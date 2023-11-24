from typing import Any
import sqlite3
from fastapi import Depends, HTTPException, Header, status, APIRouter
from http import HTTPStatus
from .Dynamo import DYNAMO_TABLENAMES
from .models import Personnel
from .dependency_injection import *
from .db_connection import get_db
from boto3.dynamodb.conditions import Key, Attr
from fastapi.responses import JSONResponse
from .enrollment_helper import enroll_students_from_waitlist, is_auto_enroll_enabled

instructor_router = APIRouter()

@instructor_router.get("/classes/{class_term_slug}/students", dependencies=[Depends(get_or_create_user)])
def get_current_enrollment(class_term_slug: str, db: Any = Depends(get_dynamo), user: Personnel = Depends(get_current_user)):
    """
    Retreive current enrollment for the classes.

    Parameters:
    - class_term_slug (string, parameter): Unique identifier (term_class) of the class.

    Returns:
    - (200) array of cwid for students enrolled in class 

    Raises:
    - HTTPException (404): If class information not found, or if current user is not instructor of class
    """

    args = class_term_slug.split("_")

    if len(args) != 2:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="invalid class term. class term must be in the format of $term_$class")

    term, _class = args
    
    query_class_information_params = {
        "KeyConditionExpression" : Key("term").eq(term) & Key("class").eq(_class),
        "FilterExpression" : Attr("instructor_id").eq(user.cwid)
    }

    class_information = db.query(tablename=DYNAMO_TABLENAMES["class"], query_params=query_class_information_params)

    if not class_information:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="class information not found")

    query_class_enrollment_params = {
        "IndexName": "class_enrollment",
        "KeyConditionExpression" : Key("term").eq(term) & Key("class").eq(_class),
        "ProjectionExpression" : "student_cwid"
    }

    class_enrollment = db.query(tablename=DYNAMO_TABLENAMES["enrollment"], query_params=query_class_enrollment_params)

    response = list(map(lambda x : {"cwid" : str(x["student_cwid"])}, class_enrollment))
    
    return JSONResponse(status_code=HTTPStatus.OK, content={"data" : response})

    # try:
    #     result = db.execute(
    #         """
    #         SELECT stu.* 
    #         FROM class sec
    #             INNER JOIN enrollment e ON sec.id = e.class_id
    #             INNER JOIN student stu ON e.student_id = stu.id 
    #         WHERE sec.id=? AND sec.instructor_id=?
    #         """, [class_id, instructor_id]
    #     )
    # except sqlite3.Error as e:
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail={"type": type(e).__name__, "msg": str(e)},
    #     )
    # finally:
    #     return {"students": result.fetchall()}

@instructor_router.get("/classes/{class_term_slug}/waitlist/", dependencies=[Depends(get_or_create_user)])
def get_waitlist(class_term_slug: str, db: Any = Depends(get_dynamo), db_redis: Any = Depends(get_redis), user: Personnel = Depends(get_current_user)):
    """
    Retreive current waiting list for the class.

    Parameters:
    - class_id (int): The ID of the class.

    Returns:
    - dict: A dictionary containing the details of the classes
    """
    args = class_term_slug.split("_")

    if len(args) != 2:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="invalid class term. class term must be in the format of $term_$class")

    term, _class = args
    
    query_class_information_params = {
        "KeyConditionExpression" : Key("term").eq(term) & Key("class").eq(_class),
        "FilterExpression" : Attr("instructor_id").eq(user.cwid)
    }

    class_information = db.query(tablename=DYNAMO_TABLENAMES["class"], query_params=query_class_information_params)

    if not class_information:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="class information not found")

    set_name = f'{_class}-{term}'
    waitlist_information = db_redis.zrange(set_name, 0, 15)

    response = list(map(lambda x : {"student_cwid" : x.decode("utf-8")}, waitlist_information))
    return JSONResponse(status_code=HTTPStatus.OK, content={"data": response})
    # try:
    #     result = db.execute(
    #         """
    #         SELECT stu.id, stu.first_name, stu.last_name, w.waitlist_date
    #         FROM class c
    #             INNER JOIN waitlist w ON c.id = w.class_id
    #             INNER JOIN student stu ON w.student_id = stu.id 
    #         WHERE c.id=? AND c.instructor_id=?
    #         ORDER BY w.waitlist_date ASC
    #         """, [class_id, instructor_id]
    #     )
    # except sqlite3.Error as e:
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail={"type": type(e).__name__, "msg": str(e)},
    #     )
    # finally:
    #     return {"students": result.fetchall()}

@instructor_router.get("/classes/{class_term_slug}/droplist/", dependencies=[Depends(get_or_create_user)])
def get_droplist(class_term_slug: str, db: Any = Depends(get_dynamo), user: Personnel = Depends(get_current_user)):
    """
    Retreive students who have dropped the class.

    Parameters:
    - class_id (int): The ID of the class.
    - instructor_id (int, In the header): A unique ID for students, instructors, and registrars.
    
    Returns:
    - dict: A dictionary containing the details of the classes
    """
    args = class_term_slug.split("_")

    if len(args) != 2:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="invalid class term. class term must be in the format of $term_$class")

    term, _class = args
    
    query_class_information_params = {
        "KeyConditionExpression" : Key("term").eq(term) & Key("class").eq(_class),
        "FilterExpression" : Attr("instructor_id").eq(user.cwid)
    }

    class_information = db.query(tablename=DYNAMO_TABLENAMES["class"], query_params=query_class_information_params)

    if not class_information:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="class information not found")
    
    query_dropped_students_params = {
        "IndexName": "class_dropped_students",
        "KeyConditionExpression" : Key("term").eq(term) & Key("class").eq(_class)
    }

    class_dropped_students = db.query(tablename=DYNAMO_TABLENAMES["droplist"], query_params=query_dropped_students_params)
    print(class_dropped_students)
    response = list(map(lambda x : {"student_cwid" : str(x["student_cwid"])}, class_dropped_students))

    return JSONResponse(status_code=HTTPStatus.OK, content={"data": response})

    # try:
    #     result = db.execute(
    #         """
    #         SELECT stu.* 
    #         FROM class c
    #             INNER JOIN droplist d ON c.id = d.class_id
    #             INNER JOIN student stu ON d.student_id = stu.id 
    #         WHERE c.id=? AND c.instructor_id=?
    #         """, [class_id, instructor_id]
    #     )
    # except sqlite3.IntegrityError as e:
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail={"type": type(e).__name__, "msg": str(e)},
    #     )
    # finally:
    #     return {"students": result.fetchall()}

@instructor_router.delete("/enrollment/{class_id}/{student_id}/administratively/", status_code=status.HTTP_200_OK)
def drop_class(
    class_id: int,
    student_id: int,
    instructor_id: int = Header(
        alias="x-cwid", description="A unique ID for students, instructors, and registrars"),
    db: sqlite3.Connection = Depends(get_db)
):
    """
    Handles a DELETE request to administratively drop a student from a specific class.

    Parameters:
    - class_id (int): The ID of the class from which the student is being administratively dropped.
    - student_id (int): The ID of the student being administratively dropped.
    - instructor_id (int, In the header): A unique ID for students, instructors, and registrars.

    Returns:
    - dict: A dictionary with the detail message indicating the success of the administrative drop.

    Raises:
    - HTTPException (409): If there is a conflict in the delete operation.
    """
    try:
        curr = db.execute(
            """
            DELETE 
            FROM enrollment
            WHERE class_id = ? AND student_id=? 
                AND class_id IN (SELECT id 
                                    FROM "class" 
                                    WHERE id=? AND instructor_id=?);
            """, [class_id, student_id, class_id, instructor_id])

        if curr.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Record Not Found"
            )
        
        db.execute(
            """
            INSERT INTO droplist (class_id, student_id, drop_date, administrative) 
            VALUES (?, ?, datetime('now'), 1);
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