import json
import re
from omegaml.backends.genai.index import VectorStoreBackend
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, text, ForeignKey, select
from sqlalchemy.orm import Session, relationship


class PGVectorBackend(VectorStoreBackend):
    """
    docker run pgvector/pgvector:pg16
    """
    KIND = 'pgvector.conx'
    PROMOTE = 'metadata'

    @classmethod
    def supports(cls, obj, name, insert=False, data_store=None, model_store=None, *args, **kwargs):
        return _is_valid_url(obj)  # or data_store.exists(name)

    def insert_chunks(self, chunks, name, embeddings, attributes, **kwargs):
        collection, vector_size, model = self._get_collection(name)
        Document, Chunk = self._create_collection(name, collection, vector_size, **kwargs)
        Session = self._get_connection(name, session=True)
        with Session as session:
            source = (attributes or {}).pop('source', None)
            attributes = json.dumps(attributes or {})
            doc = Document(source=source, attributes=attributes)
            session.add(doc)
            for text, embedding in zip(chunks, embeddings):
                chunk = Chunk(document=doc, text=text, embedding=embedding)
                session.add(chunk)
            session.commit()

    def find_similar(self, name, obj, top=5, filter=None, distance=None, **kwargs):
        collection, vector_size, model = self._get_collection(name)
        Document, Chunk = self._create_collection(name, collection, vector_size)
        Session = self._get_connection(name, session=True)
        METRIC_MAP = {
            'l2': lambda obj: Chunk.embedding.l2_distance(obj),
            'cos': lambda obj: Chunk.embedding.l2_distance(obj),
        }
        with Session as session:
            distance = METRIC_MAP[distance or 'l2'](obj)
            chunks = (select(Document.id,
                             Document.source,
                             Document.attributes,
                             Chunk.text,
                             # Chunk.embedding,
                             distance.label('distance'))
                      .join(Chunk.document)
                      .order_by(distance))
            if isinstance(top, int) and top > 0:
                chunks = chunks.limit(top)
            results = session.execute(chunks)
            data = list(results.mappings().all())
        return data

    def delete(self, name, obj=None, filter=None, **kwargs):
        collection, vector_size, model = self._get_collection(name)
        Document, Chunk = self._create_collection(name, collection, vector_size, **kwargs)
        Session = self._get_connection(name, session=True)
        with Session as session:
            session.query(Chunk).delete()
            session.query(Document).delete()
            session.commit()

    def _create_collection(self, name, collection, vector_size, **kwargs):
        from sqlalchemy.orm import declarative_base
        Base = declarative_base()
        collection = collection or self._default_collection(name)
        docs_table = f'{collection}_docs'
        chunks_table = f'{docs_table}_chunks'

        class Document(Base):
            __tablename__ = docs_table
            id = Column(Integer, primary_key=True)
            source = Column(String)
            attributes = Column(String)

        class Chunk(Base):
            __tablename__ = chunks_table
            id = Column(Integer, primary_key=True)
            text = Column(String)
            embedding = Column(Vector(vector_size))
            document_id = Column(Integer, ForeignKey(f'{docs_table}.id'))
            document = relationship('Document')

        Session = self._get_connection(name, session=True)
        with Session as session:
            session.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
            session.commit()
            Base.metadata.create_all(session.get_bind())
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
