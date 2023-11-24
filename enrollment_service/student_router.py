from typing import Annotated, Any
import sqlite3
from fastapi import Depends, HTTPException, Header, Body, status, APIRouter, Request
from .db_connection import get_db
from .enrollment_helper import enroll_students_from_waitlist, is_auto_enroll_enabled
from .dependency_injection import *
from .models import Personnel, Settings
from .Dynamo import DYNAMO_TABLENAMES
from http import HTTPStatus
import time
from boto3.dynamodb.conditions import Key, Attr
from fastapi.responses import JSONResponse


WAITLIST_CAPACITY = 15
MAX_NUMBER_OF_WAITLISTS_PER_STUDENT = 3

student_router = APIRouter()

@student_router.get("/classes/available/", dependencies=[Depends(get_or_create_user)])
def get_available_classes(db: Any = Depends(get_dynamo), user: Personnel = Depends(get_current_user)):
    '''
    EXAMPLE ONLY (please reimplement this endpoint)
    requirements:
        - "x-cwid", "x-first-name", "x-last-name", "x-roles" headers from krakend must be propagated

    example of dependency injection usage:
        1: "dependencies = [get_or_create_user]" -> this function retrieves or create user information based on 
            the propagated headers. (syncs with user db). user info is stored in request state
        2: get_dynamo -> abstraction to make dynamo accesible within the endpoint. the dynamo wrapper instance was 
            instantiated in app.py and already stored in the app state. this function just returns the object

            **why are we reusing the same instance of dynamo wrapper?
              - botocore has a built in db connection pool, of default 10 connections. that's why we only
                need one instance for the dynamo wrapper

        3: get_current_user -> abstraction to make current user accessible within the endpoint. this function just returns
            the user object saved in request state from get_or_create_user 
    '''
    return {"user" : user.cwid}
# def get_available_classes(db: sqlite3.Connection = Depends(get_db),  student_id: int = Header(
#         alias="x-cwid", description="A unique ID for students, instructors, and registrars")):
#     """
#     Retreive all available classes.

#     Returns:
#     - dict: A dictionary containing the details of the classes
#     """
#     print(student_id)
#     try:
#         classes = db.execute(
#             """
#             SELECT c.*
#             FROM "class" as c
#             WHERE datetime('now') BETWEEN c.enrollment_start AND c.enrollment_end 
#                 AND (
#                         (c.room_capacity > 
#                             (SELECT COUNT(enrollment.student_id)
#                             FROM enrollment
#                             WHERE class_id=c.id) > 0) 
#                         OR ((SELECT COUNT(waitlist.student_id)
#                             FROM waitlist
#                             WHERE class_id=c.id) < ?)
#                     );
#             """, [WAITLIST_CAPACITY]
#         )
#     except sqlite3.Error as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail={"type": type(e).__name__, "msg": str(e)},
#         )
#     finally:
#         return {"classes": classes.fetchall()}

@student_router.post("/enrollment/{class_term_slug}", dependencies=[Depends(get_or_create_user)])
def enroll(class_term_slug: str, db: Any = Depends(get_dynamo), db_redis: Any = Depends(get_redis), user: Personnel = Depends(get_current_user)):
    """
    Student enrolls in a class

    Parameters:
    - class_term_slug (string, parameter): The unique identifier (term_class) of the class where students will be enrolled.    

    Returns:
    - HTTP_201_CREATED on success

    Raises:
    - HTTPException (400): If there are no available seats.
    - HTTPException (404): If the specified class does not exist.
    - HTTPException (403): If student participates in more than 3 waitlists.
    - HTTPException (409): If a conflict occurs (e.g., The student has already enrolled into the class).
    - HTTPException (500): If there is an internal server error.
    """

    args = class_term_slug.split("_")

    if len(args) != 2:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="invalid class term. class term must be in the format of $term_$class")

    term, _class = args

    get_class_params = {
        "Get" : {
            "TableName" : DYNAMO_TABLENAMES["class"],
            "Key" : {
                "term" : term,
                "class" : _class
            }
        }
    }

    get_student_enrollment_params = {
        "Get" : {
            "TableName" : DYNAMO_TABLENAMES["enrollment"],            
            "Key" : {
                "term" : term,
                "enrollment_slug" : f'{_class}-{user.cwid}'                
            }
        }
    }

    get_waitlist_participation_params = {
        "Get" : {
            "TableName" : DYNAMO_TABLENAMES["waitlist_participation"],
            "Key" : {
                "cwid" : user.cwid,
                "term" : term
            }
        }
    }

    get_class_enrollment_params = {
        "IndexName": "class_enrollment",
        "KeyConditionExpression" : Key("term").eq(term) & Key("class").eq(_class)
    }
    
    query_results = db.transact_get_items(transact_items=[get_class_params, get_student_enrollment_params, get_waitlist_participation_params])

    if not query_results[0]:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="class information not found")

    if query_results[1]:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="you are already enrolled in this class")
    
    
    class_enrollment_count = len(db.query(tablename="Enrollment", query_params=get_class_enrollment_params))

    if class_enrollment_count < query_results[0]["Item"]["room_capacity"]:
        
        new_enrollment_params = {
            "Put" : {
                "TableName" : DYNAMO_TABLENAMES["enrollment"],
                "Item" : {
                    "term" : term,
                    "enrollment_slug" : f'{_class}-{user.cwid}',
                    "student_cwid": user.cwid,
                    "class" : _class
                }
            }
        }

        update_enrollment_count_params = {
            "Update" : {
                "TableName" : DYNAMO_TABLENAMES["class"],
                "Key" : {
                            "term" : term,
                            "class" : _class
                        },
                "UpdateExpression" : 'SET #enrollment_count = #enrollment_count + :val' ,
                "ExpressionAttributeValues": {
                    ":val" : 1           
                },
                "ExpressionAttributeNames": {
                    "#enrollment_count" : "enrollment_count",            
                }                            
            }
        }

        if db.transact_write_items(transact_items=[new_enrollment_params, update_enrollment_count_params]):        
            return JSONResponse(status_code=HTTPStatus.CREATED, content={"message": f'Enrolled in {_class}({term}) successfully'})



    set_name = f'{_class}-{term}'
    is_student_waitlisted = db_redis.zrank(set_name, user.cwid) != None

    if is_student_waitlisted:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="You are currently waitlisted for this class")
    
    if query_results[2] and query_results[2]["Item"]["count"] >= MAX_NUMBER_OF_WAITLISTS_PER_STUDENT:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=f'you cannot participate in more than {MAX_NUMBER_OF_WAITLISTS_PER_STUDENT} waitlists')

    waitlist_size = db_redis.zcard(set_name)

    if waitlist_size < WAITLIST_CAPACITY:

        update_waitlist_participation_params = {
            "Update" : {"Key" : {
                            "cwid" : user.cwid,
                            "term" : term
                        },
                        "UpdateExpression" : 'SET #count = #count + :val' ,
                        "ExpressionAttributeValues": {
                            ":val" : 1           
                        },
                        "ExpressionAttributeNames": {
                            "#count" : "count",            
                        },                                
                    }
        }

        
        if db.update_item(tablename=DYNAMO_TABLENAMES["waitlist_participation"], update_params=update_params):
            db_redis.zadd(set_name, {user.cwid : round(time.time() * 1000)})

            return JSONResponse(status_code=HTTPStatus.CREATED, content={"detail" : f'You are currently placed {waitlist_size+1}/{WAITLIST_CAPACITY} on the waitlist'})

    return HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="class is full")


    


    # try:
    #     class_info = db.execute(
    #         """
    #         SELECT id, course_start_date, enrollment_start, enrollment_end, datetime('now') AS datetime_now, 
    #                 (room_capacity - COUNT(enrollment.class_id)) AS available_seats
    #         FROM class LEFT JOIN enrollment ON class.id = enrollment.class_id 
    #         WHERE class.id = ?;
    #         """, [class_id]).fetchone()

    #     if not class_info["id"]:
    #         raise HTTPException(
    #             status_code=status.HTTP_404_NOT_FOUND, detail="Class Not Found")

    #     if not (class_info["enrollment_start"] <= class_info["datetime_now"] <= class_info["enrollment_end"]):
    #         raise HTTPException(
    #             status_code=status.HTTP_400_BAD_REQUEST, detail="Not Available At The Moment")

    #     # Insert student if not exists
    #     db.execute(
    #         """
    #         INSERT OR IGNORE INTO student (id, first_name, last_name)
    #         VALUES (?, ?, ?);
    #         """, [student_id, first_name, last_name])

    #     if class_info["available_seats"] <= 0:
    #         # CHECK THE WAITING LIST CONDITIONS
    #         #   1. students may not be on more than 3 waiting lists
    #         #   2. Waitlist capacity limit

    #         result = db.execute(
    #             """
    #             SELECT * 
    #             FROM 
    #                 (
    #                     SELECT COUNT(class_id) AS num_waitlists_student_is_on 
    #                     FROM waitlist 
    #                     WHERE student_id = ?
    #                 ), 
    #                 (
    #                     SELECT COUNT(student_id) AS num_students_on_this_waitlist 
    #                     FROM waitlist 
    #                     WHERE class_id = ?
    #                 );
    #             """, [student_id, class_id]).fetchone()

    #         if int(result["num_waitlists_student_is_on"]) >= MAX_NUMBER_OF_WAITLISTS_PER_STUDENT:
    #             raise HTTPException(
    #                 status_code=status.HTTP_400_BAD_REQUEST, 
    #                 detail=f"Cannot exceed {MAX_NUMBER_OF_WAITLISTS_PER_STUDENT} waitlists limit")
            
    #         if int(result["num_students_on_this_waitlist"]) >= WAITLIST_CAPACITY:
    #             raise HTTPException(
    #                 status_code=status.HTTP_400_BAD_REQUEST, detail="No open seats and the waitlist is also full")
            
    #         # PASS THE CONDITIONS. LET'S ADD STUDENT TO WAITLIST
    #         db.execute(
    #             """
    #             INSERT INTO waitlist(class_id, student_id, waitlist_date) 
    #             VALUES(?, ?, datetime('now'))
    #             """, [class_id, student_id]
    #         )
    #     else:
    #         # ----- INSERT INTO ENROLLMENT TABLE -----
    #         db.execute(
    #             """
    #             INSERT INTO enrollment(class_id, student_id, enrollment_date) 
    #             VALUES(?, ?, datetime('now'))
    #             """, [class_id, student_id]
    #         )

    #     db.commit()
    # except sqlite3.IntegrityError as e:
    #     raise HTTPException(status_code=status.HTTP_409_CONFLICT,
    #                         detail="The student has already enrolled into the class")

    # except HTTPException as e:
    #     raise HTTPException(status_code=e.status_code, detail=str(e.detail))

    # return {"detail": "success"}

@student_router.delete("/enrollment/{class_id}", status_code=status.HTTP_200_OK)
def drop_class(
    class_id: int,
    student_id: int = Header(
        alias="x-cwid", description="A unique ID for students, instructors, and registrars"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    Handles a DELETE request to drop a student (himself/herself) from a specific class.

    Parameters:
    - class_id (int): The ID of the class from which the student wants to drop.
    - student_id (int, in the header): A unique ID for students, instructors, and registrars.

    Returns:
    - dict: A dictionary with the detail message indicating the success of the operation.

    Raises:
    - HTTPException (409): If a conflict occurs
    """
    try:
        curr = db.execute(
            "DELETE FROM enrollment WHERE class_id=? AND student_id=?", [class_id, student_id])

        if curr.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Record Not Found"
            )
        
        db.execute(
            """
            INSERT INTO droplist (class_id, student_id, drop_date, administrative) 
            VALUES (?, ?, datetime('now'), 0);
            """, [class_id, student_id]
        )

        db.commit()

        # Trigger auto enrollment
        if is_auto_enroll_enabled(db):        
            enroll_students_from_waitlist(db, [class_id])

    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": type(e).__name__, "msg": str(e)},
        )

    return {"detail": "Item deleted successfully"}

@student_router.get("/waitlist/{class_id}/position/")
def get_current_waitlist_position(
    class_id:int,
    student_id: int = Header(
        alias="x-cwid", description="A unique ID for students, instructors, and registrars"),
    db: sqlite3.Connection = Depends(get_db)):
    """
    Retreive all available classes.

    Returns:
    - dict: A dictionary containing the details of the classes

    Raises:
    - HTTPException (404): If record not found
    """
    try:
        result = db.execute(
            """
            SELECT COUNT(student_id)
            FROM waitlist
            WHERE class_id=? AND 
                waitlist_date <= (SELECT waitlist_date 
                                    FROM waitlist
                                    WHERE class_id=? AND 
                                            student_id=?)
            ;
            """, [class_id, class_id, student_id]
        ).fetchone()

        if result[0] == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Record Not Found"
            )
        return {"position": result[0]}
        
    except sqlite3.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": type(e).__name__, "msg": str(e)},
        )

@student_router.delete("/waitlist/{class_id}/", status_code=status.HTTP_200_OK)
def remove_from_waitlist(
    class_id: int,
    student_id: int = Header(
        alias="x-cwid", description="A unique ID for students, instructors, and registrars"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    Students remove themselves from waitlist

    Parameters:
    - class_id (int): The ID of the class from which the student wants to drop.
    - student_id (int, in the header): A unique ID for students, instructors, and registrars.

    Returns:
    - dict: A dictionary with the detail message indicating the success of the operation.

    Raises:
    - HTTPException (409): If a conflict occurs
    """
    try:
        curr = db.execute(
            "DELETE FROM waitlist WHERE class_id=? AND student_id=?", [class_id, student_id])

        if curr.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Record Not Found"
            )

    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": type(e).__name__, "msg": str(e)},
        )

    return {"detail": "Item deleted successfully"}