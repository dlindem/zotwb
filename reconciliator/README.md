Fork from https://github.com/wetneb/openrefine-wikibase. MIT license
Many thanks to user wetneb.

Configuring for other Wikibase instances than Wikidata
------------------------------------------------------

This service can be configured to run against another Wikibase instance than Wikidata. The Wikibase instance will need to have an associated SPARQL Query Service, and some properties and items will need to be set up. All the relevant values must be configured in the `config.py` file, and an example of this file for Wikidata is provided in `config_wikidata.py`.

Running with Docker
-------------------

You can run this service with docker. First, clone the repository and go to its root directory:

```
git clone https://github.com/wetneb/openrefine-wikibase
cd openrefine-wikibase
```

Then, copy the sample `config_docker.py` to `config.py` and modify the copy to point to the Wikibase instance of your choice.

Finally, start the service:
```
docker-compose up
```

On Windows you will need to accept the Windows Firewall popup to expose the port 8000 where the service runs.

You can then access the landing page of your new reconciliation service at `http://localhost:8000/`.

To use it in OpenRefine, you can add the reconciliation service (in the "Start reconciling" dialog) with the address "http://localhost:8000/en/api". You can then use this reconciliation service to match data to items stored in your Wikibase instance.

Running manually
----------------

It is possible to run this web service locally. You will need Python 3.7 or later and a redis instance.

* Clone this repository, either with git (`git clone https://github.com/wetneb/openrefine-wikibase`) or by downloading the repository from Github as an archive
* It is recommended to set up a virtualenv to isolate the dependencies of the software from the other python packages installed on your computer. On a UNIX system, `virtualenv .venv` and `source .venv/bin/activate` will do. On a Windows system, `python.exe
  -m venv venv` followed by `venvname\Scripts\activate` should work.
* Install the Python dependencies with `pip install -r requirements.txt`
* Copy the configuration file provided: `cp config_wikidata.py config.py` (`copy config_wikidata.py config.py` on Windows)
* Edit the configuration file `config.py` so that `redis_client` contains the correct settings to access your redis instance. The default parameters should be fine if you are running redis locally on the default port.
* Finally, run the instance with `python app.py`. The service will be available at `http://localhost:8000/en/api`.


On Debian-based systems, it looks as follows:
```
sudo apt-get install git redis-server python3 virtualenv
git clone https://github.com/wetneb/openrefine-wikibase
cd openrefine-wikibase
virtualenv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config_wikidata.py config.py
python app.py
```