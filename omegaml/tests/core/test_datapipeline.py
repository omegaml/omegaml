from unittest import TestCase

import pandas as pd

from omegaml import Omega
from omegaml.datapipeline import Model, DataPipeline
from omegaml.tests.util import OmegaTestMixin


class DataPipelineTests(OmegaTestMixin, TestCase):
    def setUp(self):
        self.om = Omega()
        self.clean()
        super().setUp()

    def _setup_model(self, dburl=None, drop=True, table=None):
        class Product(Model):
            name = 'products'
            sql = '''
            select pno 
                 , name
            from :sqltable
            where pno in {pno}
            '''
            context = {}

            def transform(self, value, **kwargs):
                return value

        Product.dburl = dburl or Product.dburl
        Product.table = table

        data = [
            dict(pno=1234, name='shoe'),
            dict(pno=1235, name='t-shirt'),
        ]
        data = data * 10

        product = Product()
        if drop:
            Product().delete()
        product.insert(data)
        df = product.query(pno=[1234])
        self.assertEqual(len(df), 10)
        return Product


    def test_sqlmodel(self):
        self._setup_model()
        om = self.om
        df = om.datasets.get('products', sql='select * from :sqltable')
        self.assertEqual(len(df), 20)

    def test_chunksize(self):
        Product = self._setup_model()
        Product.chunksize = 2
        for chunk in Product().query(pno=[1234]):
            self.assertEqual(len(chunk), 2)

    def test_datapipeline(self):
        Product = self._setup_model()
        pipeline = DataPipeline(steps=[
            Product(),
        ])
        result = pipeline.process(pno=[1234])
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 10)

    def test_parallel_data_pipeline(self):
        Product = self._setup_model(dburl='sqlite:////tmp/test.sqlite', drop=True)
        pipeline = DataPipeline(steps=[
            Product(),
            lambda values, **kwargs: pd.concat(values),
        ])
        result = pipeline.map([dict(pno=[1234])])
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 10)

    def test_join_model(self):
        Product = self._setup_model(dburl='sqlite:////tmp/test.sqlite', drop=True)

        product = Product()
        df = product.join(product, on=['pno'])
        self.assertEqual(len(df), product.count(sql='select a.*, b.* from :sqltable as a join :sqltable as b on a.pno = b.pno'))






