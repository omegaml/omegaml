---
jupytext:
  cell_metadata_filter: -all
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3 (ipykernel)
  language: python
  name: python3
---
# Foo

This is a test of the foo document. asdf 

so how does this work?

````{tab} Python
```{code} python
print('hello world')
```
```` 

````{tab} bash
```bash
$ foo bar 
```

A nice bash example
````

A seperate code block. In [](#my-program), we print "hello world" 

```{code} python
:label: my-program
:caption: "This is a hello world example"
:filename: hello.py
print('hello world!')
```


This is executed code, the code is in a collapsible cell

```{code-cell}
:tags: [hide-input]
import omegaml as om
print('hello world!') 
om.datasets.list()
```

This is executed code, but only the output is shown

```{code-cell}
:tags: [remove-input]
import omegaml as om
print('hello world!') 
om.datasets.list()
```