import os
from setuptools import setup, find_packages

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='omegamlee',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    license='commercial',  # example license
    description='online machine learning environment for scikit-learn',
    long_description=README,
    url='https://omegaml.io',
    author='Patrick Senti',
    author_email='patrick.senti@omegaml.io',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: Commercial',  # example license
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        # replace these appropriately if you are using Python 3
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    install_requires=[
        'Django>=1.8,<1.9',
        'celery==4.2.1',
        'joblib>=0.9.4',
        'jupyter-client>=4.1.1',
        'pymongo>=3.2.2',
        'mongoengine>=0.10.6',
        'pandas>=0.17.1',
        'numpy>=1.16.4',
        'scipy>=0.17.0',
        'scikit-learn>=0.20',
        'tables>=3.2.2',
        'croniter>=0.3.30',
        'PyYAML>=3.11',
        'nbformat>=4.0.1',
        'nbconvert>=5.3.1',
        'appdirs==1.4.3',
        'cron-descriptor==1.2.24',
    ],
    dependency_links=[
    ]
)
