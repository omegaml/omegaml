from collections import Counter

import json
import logging
import re
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, text, ForeignKey, select, Index, LargeBinary, and_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session, relationship, declarative_base

from omegaml.backends.genai.dbmigrate import DatabaseMigrator
from omegaml.backends.genai.index import VectorStoreBackend
from omegaml.util import tryOr

logger = logging.getLogger(__name__)


class PGVectorBackend(VectorStoreBackend):
    """
    docker run pgvector/pgvector:pg16
    """
    KIND = 'pgvector.conx'
    PROMOTE = 'metadata'
    _attributes_keys = ('tags', 'source', 'type')

    @classmethod
    def supports(cls, obj, name, insert=False, data_store=None, model_store=None, meta=None, *args, **kwargs):
        valid_types = (meta is not None and isinstance(obj, (str, list, tuple, dict)))
        return valid_types or _is_valid_url(obj)

    def insert_chunks(self, chunks, name, embeddings, attributes, data=None, **kwargs):
        collection, vector_size, model = self._get_collection(name)
        Document, Chunk = self._create_collection(name, collection, vector_size, **kwargs)
        Session = self._get_connection(name, session=True)
        with Session as session:
            attributes = attributes or {}
            source = attributes.get('source', '')
            attributes.setdefault('source', source)
            attributes.setdefault('tags', [])
            doc = Document(source=source, attributes=attributes, data=data)
            session.add(doc)
            for text, embedding in zip(chunks, embeddings):
                chunk = Chunk(document=doc, text=text, embedding=embedding)
                session.add(chunk)
            session.commit()

    def list(self, name):
        """
        List all documents inside a collections
        """
        collection, vector_size, model = self._get_collection(name)
        Document, Chunk = self._create_collection(name, collection, vector_size)
        Session = self._get_connection(name, session=True)
        data = []
        with Session as session:
            query = (select(Document.id,
                            Document.source,
                            Document.attributes)
                     .order_by(Document.source))
            result = session.execute(query)
            data = list(result.mappings().all())
        return data

    def find_similar(self, name, obj, top=5, filter=None, distance=None, max_distance=None, **kwargs):
        """ Find similar documents in a collection based on the provided object.

        Args:
            name (str): The name of the collection to search in.
            obj (list or str): The object to find similar documents for. If a string, it will be embedded.
            top (int): The number of top similar documents to return.
            filter (dict): Optional filter criteria to apply to the search. Filters for the 'tags', 'source', and 'type'
               keys will be applied to the 'attributes' field of the documents. This can be configured by setting
               the '_attributes_keys' class variable to the desired keys or by expicitely passsing the filter as the
                'attributes' key in the filter dictionary.
            distance (str): The distance metric to use ('l2' or 'cos'). Defaults to 'l2'.
            max_distance (float): Optional maximum distance to filter results.
            **kwargs: Additional keyword arguments, if filter is not provided, kwargs will be used as
               filter.

        Returns:
            list: A list of dictionaries containing the similar documents and their attributes.
        """
        collection, vector_size, model = self._get_collection(name)
        Document, Chunk = self._create_collection(name, collection, vector_size)
        Session = self._get_connection(name, session=True)
        METRIC_MAP = {
            'l2': lambda target: Chunk.embedding.l2_distance(target),
            'cos': lambda target: Chunk.embedding.cosine_distance(target),
        }
        metric = distance or 'l2'
        filter = filter or kwargs
        with Session as session:
            distance_fn = METRIC_MAP[metric]
            query = (select(Document.id,
                            Document.source,
                            Document.attributes,
                            Chunk.text,
                            distance_fn(obj).label('distance'))
                     .join(Chunk.document))
            attributes_filter = filter.get('attributes', None)
            attributes_filter = attributes_filter or {k: v for k, v in (filter or {}).items() if
                                                      k in self._attributes_keys}
            # add attributes filter
            filters = []
            for key, value in attributes_filter.items():
                if isinstance(value, list):
                    # Use a lateral join for the IN clause
                    filters.append(Document.attributes.contains({key: value}))
                else:
                    filters.append(Document.attributes[key].astext == str(value))
            if filters:
                query = query.where(and_(*filters))
            # Add max_distance filter if provided
            if max_distance is not None:
                query = query.where(distance_fn(obj) <= max_distance)
            query = query.order_by('distance')
            logger.debug(f'PGVector query: {query.compile()} {query.compile().params}')
            if isinstance(top, int) and top > 0:
                query = query.limit(top)
            results = session.execute(query)
            data = list(results.mappings().all())
        return data

    def embeddings(self, name):
        """
        List all embeddings inside a collection
        """
        collection, vector_size, model = self._get_collection(name)
        Document, Chunk = self._create_collection(name, collection, vector_size)
        Session = self._get_connection(name, session=True)
        data = []
        with Session as session:
            query = (select(Chunk.id,
                            Chunk.text,
                            Chunk.embedding,
                            Document.source,
                            Document.attributes)
                     .join(Chunk.document)
                     .order_by(Document.source))
            result = session.execute(query)
            data = list(result.mappings().all())
        return data

    def attributes(self, name, key=None):
        """
        List all attributes inside a collection

        Args:
            name (str): The name of the collection to search in.
            key (str, optional): If provided, filter the attributes by this key.

        Returns:
            dict: A dictionary where keys are attribute names and values are dictionaries of attribute counts
        """
        collection, vector_size, model = self._get_collection(name)
        Document, Chunk = self._create_collection(name, collection, vector_size)
        Session = self._get_connection(name, session=True)
        data = []
        with Session as session:
            # this failed using sqlalchemy orm, so using raw SQL
            filter = 'key = :key_filter' if key else 'TRUE'
            query = text(f"""
                    SELECT
                        key,
                        value,
                        COUNT(*) AS count
                    FROM
                        {Document.__tablename__} AS docs,
                        jsonb_each(docs.attributes) AS kv(key, value_array)
                    LEFT JOIN LATERAL (
                        SELECT
                            value_array::text AS value
                        WHERE
                            jsonb_typeof(value_array) = 'string' OR
                            jsonb_typeof(value_array) = 'number' OR
                            jsonb_typeof(value_array) = 'boolean'
                        UNION ALL
                        SELECT
                            jsonb_array_elements_text(value_array) AS value
                        WHERE
                            jsonb_typeof(value_array) = 'array'
                    ) AS values ON TRUE
                    WHERE
                         {filter}
                    GROUP BY
                        key, value
                    ORDER BY
                        key, value;
                """)
            result = session.execute(query, {'key_filter': key} if key else {})
            data = list(row for row in result.all())
            results = {}
            for key, value, count in data:
                counter = results.setdefault(key, Counter())
                # remove string quotes safely
                # -- rationale: without this value_array::text in above SQL adds quotes to strings, e.g. '' => '""'
                #               json.loads() removes the quotes safely
                value = tryOr(lambda: json.loads(value), value)
                counter[value] += count
            results = {key: dict(counts) for key, counts in results.items()}
        return results

    def delete(self, name, obj=None, filter=None, drop=False, **kwargs):
        collection, vector_size, model = self._get_collection(name)
        Session = self._get_connection(name, session=True)
        Document, Chunk = self._create_collection(name, collection, vector_size, **kwargs)
        if drop:
            with Session as session:
                Chunk.__table__.drop(session.get_bind(), checkfirst=False)
                Document.__table__.drop(session.get_bind(), checkfirst=False)
            return
        with Session as session:
            # get documents
            if isinstance(obj, (dict, RowMapping)):
                docs_query = select(Document.id).where(Document.id == obj['id'])
            elif isinstance(obj, int):
                docs_query = select(Document.id).where(Document.id == obj)
            elif isinstance(obj, str):
                docs_query = select(Document.id).where(Document.source == obj)
            else:
                docs_query = select(Document.id)
            doc_ids = session.execute(docs_query).scalars().all()
            if doc_ids:
                session.query(Chunk).filter(Chunk.document_id.in_(doc_ids)).delete(synchronize_session='fetch')
                session.query(Document).filter(Document.id.in_(doc_ids)).delete(synchronize_session='fetch')
            session.commit()

    def _create_collection(self, name, collection, vector_size, **kwargs):
        Base = declarative_base()
        collection = collection or self._default_collection(name)
        docs_table = f'{collection}_docs'
        chunks_table = f'{docs_table}_chunks'

        class Document(Base):
            __tablename__ = docs_table
            id = Column(Integer, primary_key=True)
            source = Column(String)
            attributes = Column(JSONB, nullable=True)
            data = Column('data', String().with_variant(LargeBinary, 'postgresql'))

        class Chunk(Base):
            __tablename__ = chunks_table

            id = Column(Integer, primary_key=True)
            text = Column(String)
            embedding = Column(Vector(vector_size))
            document_id = Column(Integer, ForeignKey(f'{docs_table}.id'))
            document = relationship('Document')
            # attributes = Column(String)

        with self._get_connection(name, session=True) as session:
            session.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
            session.commit()
            Base.metadata.create_all(session.get_bind())
            session.commit()
            migrator = DatabaseMigrator(session.connection())
            migrator.run_migrations([Document, Chunk])
        with self._get_connection(name, session=True) as session:
            try:
                index = Index(
                    'l2_index',
                    Chunk.embedding,
                    postgresql_using='hnsw',
                    postgresql_with={'m': 16, 'ef_construction': 64},
                    postgresql_ops={'embedding': 'vector_l2_ops'}
                )
                index.create(session.get_bind())
            except Exception as e:
                pass
            session.commit()
        return Document, Chunk

    def _get_connection(self, name, session=False):
        from sqlalchemy import create_engine
        meta = self.data_store.metadata(name)
        connection_str = meta.kind_meta['connection']
        connection_str = connection_str.replace('pgvector', 'postgresql').replace('sqla+', '')
        import sqlalchemy
        # https://docs.sqlalchemy.org/en/14/changelog/migration_20.html
        kwargs = {} if sqlalchemy.__version__.startswith('2.') else dict(future=True)
        engine = create_engine(connection_str, **kwargs)
        if session:
            connection = Session(bind=engine)
        else:
            connection = engine.connect()
        return connection


def _is_valid_url(url):
    return isinstance(url, str) and re.match(r'(sqla\+)?pgvector://', str(url))
