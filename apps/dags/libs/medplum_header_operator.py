from airflow.models import BaseOperator
from libs.get_medplum_token import get_token
from datetime import timedelta

class MedplumHeaderOperator(BaseOperator):
    """
    Opérateur pour récupérer un token Medplum et générer des headers d'authentification.

    Args:
        scope (list): Liste des scopes nécessaires pour le token (ex: ["object:list"]).
    """
    def __init__(self, scope, *, retries=3, retry_delay=timedelta(minutes=1), **kwargs):
        super().__init__(
            retries=retries, 
            retry_delay=retry_delay, 
            **kwargs)
        self.scope = scope


    def execute(self, context):
        try:
            token = get_token(self.scope)
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            }
            return headers
        except Exception as e:
            self.log.error(f"Échec de la récupération du token : {e}")
            raise