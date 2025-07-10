import json
import re
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, text, ForeignKey, select, Index, LargeBinary
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session, relationship, declarative_base

from omegaml.backends.genai.dbmigrate import DatabaseMigrator
from omegaml.backends.genai.index import VectorStoreBackend


class PGVectorBackend(VectorStoreBackend):
    """
    docker run pgvector/pgvector:pg16
    """
    KIND = 'pgvector.conx'
    PROMOTE = 'metadata'

    @classmethod
    def supports(cls, obj, name, insert=False, data_store=None, model_store=None, meta=None, *args, **kwargs):
        valid_types = (meta is not None and isinstance(obj, (str, list, tuple, dict)))
        return valid_types or _is_valid_url(obj)

    def insert_chunks(self, chunks, name, embeddings, attributes, data=None, **kwargs):
        collection, vector_size, model = self._get_collection(name)
        Document, Chunk = self._create_collection(name, collection, vector_size, **kwargs)
        Session = self._get_connection(name, session=True)
        with Session as session:
            source = (attributes or {}).pop('source', None)
            source = str(source) if source else ''
            attributes = json.dumps(attributes or {})
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

    def find_similar(self, name, obj, top=5, filter=None, distance=None, **kwargs):
        collection, vector_size, model = self._get_collection(name)
        Document, Chunk = self._create_collection(name, collection, vector_size)
        Session = self._get_connection(name, session=True)
        METRIC_MAP = {
            'l2': lambda target: Chunk.embedding.l2_distance(target),
            'cos': lambda target: Chunk.embedding.cosine_distance(target),
        }
        metric = distance or 'l2'
        with Session as session:
            distance_fn = METRIC_MAP[metric]
            chunks = (select(Document.id,
                             Document.source,
                             Document.attributes,
                             Chunk.text,
                             # Chunk.embedding,
                             distance_fn(obj).label('distance'))
                      .join(Chunk.document)
                      .order_by(distance))
            if isinstance(top, int) and top > 0:
                chunks = chunks.limit(top)
            results = session.execute(chunks)
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
            attributes = Column(String)
            data = Column('data', String().with_variant(LargeBinary, 'postgresql'))

        class Chunk(Base):
            __tablename__ = chunks_table

            id = Column(Integer, primary_key=True)
            text = Column(String)
            embedding = Column(Vector(vector_size))
            document_id = Column(Integer, ForeignKey(f'{docs_table}.id'))
            document = relationship('Document')

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
