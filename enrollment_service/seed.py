from .Dynamo import Dynamo
from .models import Settings

settings = Settings()
dynamo = Dynamo(config=settings)

create_class_table_params = {
    "TableName":'Class',
    "KeySchema":[
        {
            'AttributeName': 'term',
            'KeyType': 'HASH'
        },
        {
            'AttributeName': 'class',
            'KeyType': 'RANGE'
        }
    ],
    "AttributeDefinitions":[
        {
            'AttributeName': 'term',
            'AttributeType': 'S'
        },
        {
            'AttributeName': 'department',
            'AttributeType': 'S'
        },
        {
            'AttributeName': 'class',
            'AttributeType': 'S'
        }
    ],
    "LocalSecondaryIndexes" : [
        {
            "IndexName" : "department_classes",
            "KeySchema" : [
                {
                    "AttributeName" : "term",
                    "KeyType" : "HASH"
                },
                {
                    "AttributeName" : "department",
                    "KeyType" : 'RANGE'
                }
            ],
            "Projection" : {
                "ProjectionType" : "KEYS_ONLY"
            }
        }
    ],
    "ProvisionedThroughput": {"ReadCapacityUnits": 3, "WriteCapacityUnits": 3},
}

create_personnel_table_params = {
    "TableName":'Personnel',
    "KeySchema":[
        {
            'AttributeName': 'cwid',
            'KeyType': 'HASH'
        }
    ],
    "AttributeDefinitions":[
        {
            'AttributeName': 'cwid',
            'AttributeType': 'N'
        }
    ],
    "ProvisionedThroughput": {"ReadCapacityUnits": 3, "WriteCapacityUnits": 3},
}

create_config_table_params = {
    "TableName":'Config',
    "KeySchema":[
        {
            'AttributeName': 'variable_name',
            'KeyType': 'HASH'
        }
    ],
    "AttributeDefinitions":[
        {
            'AttributeName': 'variable_name',
            'AttributeType': 'S'
        }        
    ],
    "ProvisionedThroughput": {"ReadCapacityUnits": 3, "WriteCapacityUnits": 3},
}

create_enrollment_table_params = {
    "TableName":'Enrollment',
    "KeySchema":[
        {
            'AttributeName': 'term',
            'KeyType': 'HASH'
        },
        {
            'AttributeName': 'enrollment_slug',
            'KeyType': 'RANGE'
        }
    ],
    "AttributeDefinitions":[
        {
            'AttributeName': 'term',
            'AttributeType': 'S'
        },
        {
            'AttributeName': 'enrollment_slug',
            'AttributeType': 'S'
        },
        {
            'AttributeName': 'class',
            'AttributeType': 'S'
        },
        {
            "AttributeName" : "student_cwid",
            "AttributeType" : "N"
        }
    ],
    "LocalSecondaryIndexes" : [
        {
            "IndexName" : "student_enrollment",
            "KeySchema" : [
                {
                    "AttributeName" : "term",
                    "KeyType" : "HASH"
                },
                {
                    "AttributeName" : "student_cwid",
                    "KeyType" : 'RANGE'
                }
            ],
            "Projection" : {
                "ProjectionType" : "KEYS_ONLY"
            }
        },
        {
            "IndexName" : "class_enrollment",
            "KeySchema" : [
                {
                    "AttributeName" : "term",
                    "KeyType" : "HASH"
                },
                {
                    "AttributeName" : "class",
                    "KeyType" : 'RANGE'
                }
            ],
            "Projection" : {
                "ProjectionType" : "ALL"
            }
        }
    ],
    "ProvisionedThroughput": {"ReadCapacityUnits": 3, "WriteCapacityUnits": 3},
}

create_waitlist_participation_table_params = {
    "TableName":'Waitlist_Participation',
    "KeySchema":[
        {
            'AttributeName': 'term',
            'KeyType': 'HASH'
        },
        {
            'AttributeName': 'cwid',
            'KeyType': 'RANGE'
        }
    ],
    "AttributeDefinitions":[
        {
            'AttributeName': 'term',
            'AttributeType': 'S'
        },
        {
            'AttributeName': 'cwid',
            'AttributeType': 'N'
        }
    ],
    "ProvisionedThroughput": {"ReadCapacityUnits": 3, "WriteCapacityUnits": 3},
}

create_course_table_params = {
    "TableName":'Course',
    "KeySchema":[
        {
            'AttributeName': 'department_code',
            'KeyType': 'HASH'
        },
        {
            'AttributeName': 'course_no',
            'KeyType': 'RANGE'
        }
    ],
    "AttributeDefinitions":[
        {
            'AttributeName': 'department_code',
            'AttributeType': 'S'
        },
        {
            'AttributeName': 'course_no',
            'AttributeType': 'S'
        }
    ],
    "ProvisionedThroughput": {"ReadCapacityUnits": 3, "WriteCapacityUnits": 3},
}

create_droplist_table_params = {
    "TableName" : "Droplist",
    "KeySchema" : [
        {
            "AttributeName" : "term",
            "KeyType" : "HASH"
        }, 
        {
            "AttributeName" : "dropped_slug",
            "KeyType": "RANGE"
        }
    ],
    "AttributeDefinitions" : [
        {
            "AttributeName" : "term",
            "AttributeType" : "S"
        },
        {
            "AttributeName" : "dropped_slug",
            "AttributeType" : "S"
        },
        {
            "AttributeName" : "class",
            "AttributeType" : "S"
        },
    ],
    "LocalSecondaryIndexes" : [
        {
            "IndexName" : "class_dropped_students",
            "KeySchema" : [
                {
                    "AttributeName": "term",
                    "KeyType" : "HASH"
                },
                {
                    "AttributeName": "class",
                    "KeyType" : "RANGE"
                },
            ],
            "Projection" : {
                "ProjectionType" : "ALL"
            }
        }
    ],
    "ProvisionedThroughput": {"ReadCapacityUnits": 3, "WriteCapacityUnits": 3},
}

required_tables = ["Class", "Course", "Personnel", "Config", "Enrollment", "Droplist", "Waitlist_Participation"]
existing_tables = [table.name for table in dynamo.list_tables()]

params= {
    "Class" : create_class_table_params,
    "Course" : create_course_table_params,
    "Personnel" : create_personnel_table_params,
    "Config" : create_config_table_params,
    "Enrollment" : create_enrollment_table_params,
    "Waitlist_Participation" : create_waitlist_participation_table_params,
    "Droplist" : create_droplist_table_params
}


for table in required_tables:
    if table in existing_tables:
        print(f'existing table {table} found, recreating table')
        dynamo.delete_table(table)
    dynamo.create_table(create_params=params[table])

# seeding auto_enrollment_enabled config
item = {
    "variable_name" : "auto_enrollment_enabled",
    "value" : True
}

dynamo.put_item(tablename="Config", item=item)




