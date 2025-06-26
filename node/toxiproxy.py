import requests

class ToxiproxyAPI:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.proxies = {}
    
    def create(self, name, listen, upstream):
        """Créer un nouveau proxy"""
        url = f"{self.base_url}/proxies"
        data = {
            "name": name,
            "listen": listen,
            "upstream": upstream
        }
        response = requests.post(url, json=data)
        response.raise_for_status()
        self.proxies[name] = response.json()
        return Proxy(self, name)
    
    def get(self, name):
        """Récupérer un proxy existant"""
        url = f"{self.base_url}/proxies/{name}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            self.proxies[name] = response.json()
            return Proxy(self, name)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise KeyError(f"Proxy '{name}' not found")
            raise

    def reset(self):
        """Réinitialiser tous les proxies"""
        url = f"{self.base_url}/reset"
        response = requests.post(url)
        response.raise_for_status()

class Proxy:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.toxics = ToxicsAPI(client, name)
    
    def delete(self):
        """Supprimer le proxy"""
        url = f"{self.client.base_url}/proxies/{self.name}"
        response = requests.delete(url)
        response.raise_for_status()
        if self.name in self.client.proxies:
            del self.client.proxies[self.name]

class ToxicsAPI:
    def __init__(self, client, proxy_name):
        self.client = client
        self.proxy_name = proxy_name
    
    def add(self, name, type, attributes, stream="downstream"):
        """Ajouter un toxic au proxy"""
        url = f"{self.client.base_url}/proxies/{self.proxy_name}/toxics"
        data = {
            "name": name,
            "type": type,
            "stream": stream,
            "toxicity": 1.0,
            "attributes": attributes
        }
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
    
    def get(self, name):
        """Récupérer un toxic existant"""
        url = f"{self.client.base_url}/proxies/{self.proxy_name}/toxics/{name}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    def update(self, name, **kwargs):
        """Mettre à jour un toxic existant"""
        url = f"{self.client.base_url}/proxies/{self.proxy_name}/toxics/{name}"
        response = requests.post(url, json=kwargs)
        response.raise_for_status()
        return response.json()
    
    def delete(self, name):
        """Supprimer un toxic"""
        url = f"{self.client.base_url}/proxies/{self.proxy_name}/toxics/{name}"
        response = requests.delete(url)
        response.raise_for_status()