Using omega|ml datasets for files
---------------------------------

Motivating example: Say you have a file 'test.xyz' that you want to read and write in your web application.
That's not typically a supported scenario in a containerized application as local storage is emphemeral.

For this purpose, om.datasets provides the `python.file` object kind:

1. Store a file

   ```
   # cli
   $ om datasets put /path/to/test.xyz test.xyz    # first=local path second=name in omegaml
   Metadata(name=test.xyz,bucket=omegaml,prefix=data/,kind=python.file,created=2020-12-04 17:31:01.044330)

   # python, from a local file
   [] om.datasets.put('/path/to/test.xyz', 'test.xyz')
   <Metadata: Metadata(name=test.xyz,bucket=omegaml,prefix=data/,kind=python.file,created=2020-12-04 17:31:35.339009)>

   # python, from a file-like object
   [] with open('test.xyz', 'rb') as fin:
         om.datasets.put(fin, 'test.xyz')
   ```

2. Retrieve the file back

   ```
   # cli
   $ om datasets get test.xyz /path/to/local/test.xyz

   # python, process the file
   [] file_obj = om.datasets.get('test.xyz')
      data = file_obj.read()
      file_obj.close()

   # python, store the file
   [] om.datasets.get('test.xyz', local='./test.yz', open_kwargs={})
   ```

How this works
--------------

* on .put(): A local file or a file-like object is read as a binary stream and
             written to a GridFS file.

* on .get(): A file-like object is returned, unless the local= and open_kwargs
             arguments are specified. In this case, the file is written and the
             local path is returned.


Reference
---------

```
[] om.datasets.help(kind='python.file`)
Help on PythonRawFileBackend in module omegaml.backends.rawfiles object:

class PythonRawFileBackend(omegaml.backends.basedata.BaseDataBackend)
 |  OmegaStore backend to support arbitrary files
 |
 |  Method resolution order:
 |      PythonRawFileBackend
 |      omegaml.backends.basedata.BaseDataBackend
 |      omegaml.backends.basecommon.BackendBaseCommon
 |      builtins.object
 |
 |  Methods defined here:
 |
 |  get(self, name, local=None, mode='wb', open_kwargs=None, **kwargs)
 |      get a stored file as a file-like object with binary contents or a local file
 |
 |      Args:
 |          name (str): the name of the file
 |          local (str): if set the local path will be created and the file
 |             stored there. If local does not have an extension it is assumed
 |             to be a directory name, in which case the file is stored as the
 |             same name.
 |          mode (str): the mode to use on .open() for the local file
 |          open_kwargs (dict): the kwargs to use .open() for the local file
 |          **kwargs: any kwargs passed to datasets.metadata()
 |
 |      Returns:
 |          the file-like output handler (local is None)
 |          the path to the local file (local is given)
 |
 |      See also:
 |          https://docs.python.org/3/glossary.html#term-file-object
 |          https://docs.python.org/3/glossary.html#term-binary-file
 |
 |  put(self, obj, name, attributes=None, encoding=None, **kwargs)
 |      put an obj
```
