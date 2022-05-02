from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import Response
from starlette.status import HTTP_204_NO_CONTENT

from empire.server.database import models
from empire.server.server import main
from empire.server.v2.api.EmpireApiRouter import APIRouter
from empire.server.v2.api.jwt_auth import get_current_active_user
from empire.server.v2.api.listener.listener_dto import (
    Listener,
    ListenerPostRequest,
    Listeners,
    ListenerUpdateRequest,
    domain_to_dto_listener,
)
from empire.server.v2.api.shared_dependencies import get_db

listener_service = main.listenersv2

router = APIRouter(
    prefix="/api/v2beta/listeners",
    tags=["listeners"],
    responses={404: {"description": "Not found"}},
)


async def get_listener(uid: int, db: Session = Depends(get_db)):
    listener = listener_service.get_by_id(db, uid)

    if listener:
        return listener

    raise HTTPException(404, f"Listener not found for id {uid}")


@router.get(
    "/{uid}", response_model=Listener, dependencies=[Depends(get_current_active_user)]
)
async def read_listener(uid: int, db_listener: models.Listener = Depends(get_listener)):
    return domain_to_dto_listener(db_listener)


@router.get(
    "/", response_model=Listeners, dependencies=[Depends(get_current_active_user)]
)
async def read_listeners(db: Session = Depends(get_db)):
    listeners = list(
        map(lambda x: domain_to_dto_listener(x), listener_service.get_all(db))
    )

    return {"records": listeners}


@router.post(
    "/",
    status_code=201,
    response_model=Listener,
    dependencies=[Depends(get_current_active_user)],
)
async def create_listener(
    listener_req: ListenerPostRequest, db: Session = Depends(get_db)
):
    """
    Note: options['Name'] will be overwritten by name. When v1 api is eventually removed, it wil no longer be needed.
    :param listener_req:
    :param db
    :return:
    """
    resp, err = listener_service.create_listener(db, listener_req)

    if err:
        raise HTTPException(status_code=400, detail=err)

    return domain_to_dto_listener(resp)


@router.put(
    "/{uid}", response_model=Listener, dependencies=[Depends(get_current_active_user)]
)
async def update_listener(
    uid: int,
    listener_req: ListenerUpdateRequest,
    db: Session = Depends(get_db),
    db_listener: models.Listener = Depends(get_listener),
):
    if listener_req.enabled and not db_listener.enabled:
        # update then turn on
        resp, err = listener_service.update_listener(db, db_listener, listener_req)

        if err:
            raise HTTPException(status_code=400, detail=err)

        resp, err = listener_service.start_existing_listener(db, resp)

        if err:
            raise HTTPException(status_code=400, detail=err)

        return domain_to_dto_listener(resp)
    elif listener_req.enabled and db_listener.enabled:
        # err already running / cannot update
        raise HTTPException(
            status_code=400, detail="Listener must be disabled before modifying"
        )
    elif not listener_req.enabled and db_listener.enabled:
        # disable and update
        listener_service.stop_listener(db_listener)
        resp, err = listener_service.update_listener(db, db_listener, listener_req)

        if err:
            raise HTTPException(status_code=400, detail=err)

        return domain_to_dto_listener(resp)
    elif not listener_req.enabled and not db_listener.enabled:
        # update
        resp, err = listener_service.update_listener(db, db_listener, listener_req)

        if err:
            raise HTTPException(status_code=400, detail=err)

        return domain_to_dto_listener(resp)
    else:
        raise HTTPException(status_code=500, detail="This Shouldn't Happen")


@router.delete(
    "/{uid}",
    status_code=HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(get_current_active_user)],
)
async def delete_listener(
    uid: int,
    db: Session = Depends(get_db),
    db_listener: models.Listener = Depends(get_listener),
):
    listener_service.delete_listener(db, db_listener)
