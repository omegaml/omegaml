"""
omegaml command line module

Use this to obtain the initial .config.yml file. The userid and apikey
are provided on the web dashboard for your user.

Usage:

    .. code::

        $ python -m omegacli
        usage: __main__.py [-h] {init} ...
    
        omegaml cli
        
        positional arguments:
          {init}      commands
            init      initialize
        
        optional arguments:
          -h, --help  show this help message and exit
          
          
        $ python -m omegacli init -h
        usage: __main__.py init [-h] [--userid USERID] [--apikey APIKEY] [--url URL]
        
        optional arguments:
          -h, --help       show this help message and exit
          --userid USERID  omegaml userid
          --apikey APIKEY  omegaml apikey
          --url URL        omegaml URL
"""