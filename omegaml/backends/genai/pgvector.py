import re
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, text, ForeignKey, select
from sqlalchemy.orm import Session, relationship

from omegaml.backends.basedata import BaseDataBackend
from omegaml.backends.sqlalchemy import SQLAlchemyBackend


class PGVectorBackend(BaseDataBackend):
    """
    docker run pgvector/pgvector:pg16
    """
    KIND = 'pgvector.conx'
    PROMOTE = 'metadata'

    @classmethod
    def supports(cls, obj, name, insert=False, data_store=None, model_store=None, *args, **kwargs):
        return _is_valid_url(obj)  # or data_store.exists(name) and isinstance()

    def get(self, name, obj=None, table=None, vector_size=None, raw=False, limit=1, **kwargs):
        meta = self.data_store.metadata(name)
        table = meta.kind_meta.get('table') or self._default_table(name)
        vector_size = meta.kind_meta['tables'][table].get('vector_size')
        if obj is not None:
            data = self._get_chunks(name, obj, table, vector_size, n=limit)
            return data
        return self._get_connection(name)

    def put(self, obj, name, table=None, vector_size=None, attributes=None, append=True, **kwargs):
        meta = self.data_store.metadata(name)
        if meta is None:
            url = obj
            table = self._default_table(table or name)
            meta = self._put_as_connection(url, name, table=table,
                                           attributes=attributes, **kwargs)
        elif meta is not None:
            table = meta.kind_meta.get('table') or self._default_table(name)
            vector_size = vector_size or meta.kind_meta['tables'][table]['vector_size']
            self._put_via(obj, name, table, vector_size, **kwargs)
        else:
            raise ValueError('type {} is not supported by {}'.format(type(obj), self.KIND))
        tables = meta.kind_meta.setdefault('tables', {})
        tables[table] = {
            'vector_size': vector_size,
        }
        meta.attributes.update(attributes) if attributes else None
        return meta.save()

    def _create_table(self, name, table, vector_size, **kwargs):
        from sqlalchemy.orm import declarative_base
        Base = declarative_base()
        docs_table = table or self._default_table(name)
        chunks_table = f'{docs_table}_chunks'

        class Document(Base):
            __tablename__ = docs_table
            id = Column(Integer, primary_key=True)
            source = Column(String)

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

    def _put_via(self, obj, name, table, vector_size, chunksize=None, transform=None,
                 index_columns=None, index=True, **kwargs):
        Document, Chunk = self._create_table(name, table, vector_size, **kwargs)
        Session = self._get_connection(name, session=True)
        with Session as session:
            doc = Document(source='some source')
            session.add(doc)
            for text, embedding in obj:
                chunk = Chunk(document=doc, text=text, embedding=embedding)
                session.add(chunk)
            session.commit()

    def _put_as_data(self, url, name, cnx_name, sql=None, chunksize=None, append=True,
                     transform=None, **kwargs):
        # use the url to query the connection and store resulting data instead
        if not sql:
            raise ValueError('a valid SQL statement is required with copy=True')
        metadata = self.copy_from_sql(sql, url, name, chunksize=chunksize,
                                      append=append, transform=transform,
                                      **kwargs)
        metadata.attributes['created_from'] = cnx_name
        return metadata

    def _put_as_connection(self, url, name, attributes=None,
                           table=None, **kwargs):
        kind_meta = {
            'sqlalchemy_connection': str(url),
            'table': table,
            'kwargs': kwargs,
        }
        meta = self.data_store.metadata(name)
        if meta is not None:
            meta.kind_meta.update(kind_meta)
        else:
            meta = self.data_store.make_metadata(name, self.KIND,
                                                 kind_meta=kind_meta,
                                                 attributes=attributes)
        return meta.save()

    def _get_connection(self, name, session=False):
        from sqlalchemy import create_engine
        meta = self.data_store.metadata(name)
        connection_str = meta.kind_meta['sqlalchemy_connection']
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

    def _get_chunks(self, name, obj, table, vector_size, n=1):
        Document, Chunk = self._create_table(name, table, vector_size)
        Session = self._get_connection(name, session=True)
        with Session as session:
            chunks = session.scalars(select(Chunk).order_by(Chunk.embedding.l2_distance(obj)).limit(n))
            data = [(row.text, row.embedding) for row in chunks.all()]
        return data

    def _default_table(self, name):
        if name is None:
            return name
        if not name.startswith(':'):
            name = f'{self.data_store.bucket}_{name}'
        else:
            name = name[1:]
        return name


def _is_valid_url(url):
    return isinstance(url, str) and re.match('(sqla\+)?pgvector://', str(url))


