import boto3
from botocore.exceptions import ClientError
from .models import Settings

DYNAMO_TABLENAMES = {
    'class' : "Class",
    "course" : "Course",
    "personnel" : "Personnel",
    "enrollment" : "Enrollment",
    "config" : "Config",
    "waitlist_participation" : "Waitlist_Participation",
    "droplist" : "Droplist"
}

class Dynamo:
    def __init__ (self, config: Settings):
         self.dyn_resource = boto3.resource(
            "dynamodb",
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            region_name=config.aws_region_name,
            endpoint_url=config.endpoint_url
        )
    
    def create_table(self, create_params: dict):
        try:
            self.dyn_resource.create_table(**create_params)
            return True
        except ClientError as err:
            raise err
            
    def delete_table(self, tablename: str):
        try: 
            table = self.dyn_resource.Table(tablename)
            table.delete()
            return True
        except ClientError as err:
            raise err
    
    def list_tables(self):
        response = list(self.dyn_resource.tables.all())
        return response

    def query(self, tablename: str, query_params: dict):
         try:
              result = self.dyn_resource.Table(tablename).query(**query_params)
              items = result["Items"]

              return items
         except ClientError as err:
              raise err
    
    def put_item(self, tablename: str, item: dict):
        try:
            self.dyn_resource.Table(tablename).put_item(Item=item)
            return True

        except ClientError as err:
            raise err

    def update_item(self, tablename: str, update_params: dict):
        try:
            result = self.dyn_resource.Table(tablename).update_item(**update_params)
            return result["Attributes"]
         
        except ClientError as err:
            raise err
    
    def batch_get_item(self, query_params: dict):
        try:
            items = self.dyn_resource.batch_get_item(**query_params)
            return items["Responses"]
        except ClientError as err:
            raise err
    
    def delete_item(self, tablename: str, delete_params: dict):
        try:
            self.dyn_resource.Table(tablename).delete_item(**delete_params)
            return True
        except ClientError as err:
            raise err
    
    def transact_write_items(self, transact_items: list):
        try:
            self.dyn_resource.meta.client.transact_write_items(TransactItems=transact_items)
            return True
        except ClientError as err:
            raise err
    
    def transact_get_items(self, transact_items: list):
        try:
            result = self.dyn_resource.meta.client.transact_get_items(TransactItems=transact_items)
            return result["Responses"]
        
        except ClientError as err:
            raise err

    def __exit__(self, *args):
        self.dyn_resource.close()