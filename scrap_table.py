import json
import uuid
from datetime import datetime
from urllib.request import Request, urlopen

import boto3

TABLE_NAME = "TablaSismosIGP"
API_URL = "https://ultimosismo.igp.gob.pe/api/ultimo-sismo/ajaxb/{year}"


def lambda_handler(event, context):
    year = datetime.utcnow().year
    req = Request(
        API_URL.format(year=year),
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://ultimosismo.igp.gob.pe/productos/reportes-sismicos/",
        },
    )

    # Llamar al API que usa la página
    try:
        with urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"statusCode": 502, "body": f"Error al acceder al API del IGP: {e}"}

    # Si viene como objeto, tomar la primera lista que contenga
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), [])

    if not data:
        return {"statusCode": 404, "body": "El API no devolvió sismos"}

    # Convertir valores a string (DynamoDB no acepta float) y agregar id
    rows = []
    for i, item in enumerate(data, start=1):
        row = {k: ("" if v is None else str(v)) for k, v in item.items()}
        row["#"] = i
        row["id"] = str(uuid.uuid4())
        rows.append(row)

    table = boto3.resource("dynamodb").Table(TABLE_NAME)

    # Leer los registros anteriores (con paginación)
    old_items = []
    resp = table.scan(ProjectionExpression="id")
    old_items.extend(resp["Items"])
    while "LastEvaluatedKey" in resp:
        resp = table.scan(
            ProjectionExpression="id",
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        old_items.extend(resp["Items"])

    # Borrar los anteriores e insertar los nuevos
    with table.batch_writer() as batch:
        for it in old_items:
            batch.delete_item(Key={"id": it["id"]})
        for row in rows:
            batch.put_item(Item=row)

    return {"statusCode": 200, "body": rows}
    # Guardar los datos en DynamoDB
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('TablaWebScrapping2')

    # Eliminar todos los elementos de la tabla antes de agregar los nuevos
    scan = table.scan()
    with table.batch_writer() as batch:
        for each in scan['Items']:
            batch.delete_item(
                Key={
                    'id': each['id']
                }
            )

    # Insertar los nuevos datos
    i = 1
    for row in rows:
        row['#'] = i
        row['id'] = str(uuid.uuid4())  # Generar un ID único para cada entrada
        table.put_item(Item=row)
        i = i + 1

    # Retornar el resultado como JSON
    return {
        'statusCode': 200,
        'body': rows
    }
