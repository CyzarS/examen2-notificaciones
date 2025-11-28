"""
Lambda Handler para envío de notificaciones por correo electrónico
Escucha mensajes de SNS y envía correos usando SES
"""
import os
import json
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import logging

# Configuración de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuración del ambiente
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "noreply@example.com")
S3_BUCKET = os.getenv("S3_BUCKET", "expediente-esi3898k-examen1")

# Clientes AWS
ses_client = None
s3_client = None
cloudwatch = None

try:
    ses_client = boto3.client('ses', region_name=AWS_REGION)
    s3_client = boto3.client('s3', region_name=AWS_REGION)
    cloudwatch = boto3.client('cloudwatch', region_name=AWS_REGION)
except Exception as e:
    logger.error(f"Error initializing AWS clients: {e}")


def put_metric(metric_name: str, value: float, unit: str = 'Count', dimensions: list = None):
    """Envía métricas a CloudWatch"""
    if not cloudwatch:
        return
    
    try:
        metric_data = {
            'MetricName': metric_name,
            'Timestamp': datetime.utcnow(),
            'Value': value,
            'Unit': unit
        }
        
        if dimensions:
            metric_data['Dimensions'] = dimensions
        else:
            metric_data['Dimensions'] = [
                {'Name': 'Environment', 'Value': ENVIRONMENT}
            ]
        
        cloudwatch.put_metric_data(
            Namespace='NotificacionesAPI',
            MetricData=[metric_data]
        )
    except Exception as e:
        logger.error(f"Error sending metric: {e}")


def actualizar_metadatos_s3(rfc_cliente: str, folio_nota: str):
    """Actualiza los metadatos del PDF en S3 después de enviar notificación"""
    if not s3_client:
        return False
    
    object_key = f"{rfc_cliente}/{folio_nota}.pdf"
    
    try:
        # Obtener metadatos actuales
        response = s3_client.head_object(Bucket=S3_BUCKET, Key=object_key)
        metadata = response.get('Metadata', {})
        
        # Actualizar metadatos
        timestamp = datetime.utcnow().isoformat()
        veces_enviado = int(metadata.get('veces-enviado', '0')) + 1
        
        new_metadata = {
            'hora-envio': timestamp,
            'nota-descargada': metadata.get('nota-descargada', 'false'),
            'veces-enviado': str(veces_enviado)
        }
        
        # Copiar objeto con nuevos metadatos
        s3_client.copy_object(
            Bucket=S3_BUCKET,
            CopySource={'Bucket': S3_BUCKET, 'Key': object_key},
            Key=object_key,
            Metadata=new_metadata,
            MetadataDirective='REPLACE'
        )
        
        logger.info(f"Metadatos actualizados para {object_key}: veces-enviado={veces_enviado}")
        return True
    except ClientError as e:
        logger.error(f"Error actualizando metadatos: {e}")
        return False


def enviar_correo(destinatario: str, nombre_cliente: str, folio_nota: str, download_url: str):
    """Envía correo electrónico usando AWS SES"""
    if not ses_client:
        logger.error("SES client not initialized")
        return False
    
    subject = f"Nueva Nota de Venta - Folio {folio_nota}"
    
    # Cuerpo del correo en HTML
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9f9f9; }}
            .button {{ 
                display: inline-block; 
                padding: 12px 24px; 
                background-color: #3498db; 
                color: white; 
                text-decoration: none; 
                border-radius: 5px;
                margin: 20px 0;
            }}
            .button:hover {{ background-color: #2980b9; }}
            .footer {{ padding: 20px; text-align: center; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Nota de Venta Generada</h1>
            </div>
            <div class="content">
                <p>Estimado/a <strong>{nombre_cliente}</strong>,</p>
                
                <p>Le informamos que se ha generado una nueva nota de venta a su nombre.</p>
                
                <p><strong>Folio de la nota:</strong> {folio_nota}</p>
                <p><strong>Fecha de generación:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
                
                <p>Puede descargar su nota de venta en formato PDF haciendo clic en el siguiente enlace:</p>
                
                <p style="text-align: center;">
                    <a href="{download_url}" class="button">Descargar Nota de Venta</a>
                </p>
                
                <p>Si tiene alguna pregunta o requiere asistencia, no dude en contactarnos.</p>
                
                <p>Atentamente,<br>
                <strong>Sistema de Notas de Venta</strong></p>
            </div>
            <div class="footer">
                <p>Este es un correo automático, por favor no responda a este mensaje.</p>
                <p>© {datetime.utcnow().year} Sistema de Notas de Venta</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Cuerpo en texto plano
    text_body = f"""
    Estimado/a {nombre_cliente},

    Le informamos que se ha generado una nueva nota de venta a su nombre.

    Folio de la nota: {folio_nota}
    Fecha de generación: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

    Puede descargar su nota de venta en formato PDF en el siguiente enlace:
    {download_url}

    Si tiene alguna pregunta o requiere asistencia, no dude en contactarnos.

    Atentamente,
    Sistema de Notas de Venta
    """
    
    try:
        response = ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={
                'ToAddresses': [destinatario]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': text_body,
                        'Charset': 'UTF-8'
                    },
                    'Html': {
                        'Data': html_body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        
        logger.info(f"Correo enviado exitosamente. MessageId: {response['MessageId']}")
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"Error enviando correo: {error_code} - {error_message}")
        return False


def lambda_handler(event, context):
    """
    Handler principal de Lambda
    Procesa mensajes de SNS y envía notificaciones por correo
    """
    logger.info(f"Event received: {json.dumps(event)}")
    logger.info(f"Environment: {ENVIRONMENT}")
    
    start_time = datetime.utcnow()
    success_count = 0
    error_count = 0
    
    # Procesar registros de SNS
    for record in event.get('Records', []):
        try:
            # Extraer mensaje de SNS
            sns_message = record.get('Sns', {})
            message_body = sns_message.get('Message', '{}')
            
            # Parsear el mensaje JSON
            try:
                message_data = json.loads(message_body)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in message: {message_body}")
                error_count += 1
                continue
            
            # Extraer datos del mensaje
            cliente_email = message_data.get('cliente_email')
            cliente_nombre = message_data.get('cliente_nombre', 'Cliente')
            folio_nota = message_data.get('folio_nota')
            rfc_cliente = message_data.get('rfc_cliente')
            download_url = message_data.get('download_url')
            
            # Validar datos requeridos
            if not all([cliente_email, folio_nota, download_url]):
                logger.error(f"Missing required fields in message: {message_data}")
                error_count += 1
                put_metric('NotificationErrors', 1, dimensions=[
                    {'Name': 'Environment', 'Value': ENVIRONMENT},
                    {'Name': 'ErrorType', 'Value': 'MissingFields'}
                ])
                continue
            
            # Enviar correo
            logger.info(f"Sending email to {cliente_email} for folio {folio_nota}")
            
            if enviar_correo(cliente_email, cliente_nombre, folio_nota, download_url):
                success_count += 1
                
                # Actualizar metadatos en S3
                if rfc_cliente and folio_nota:
                    actualizar_metadatos_s3(rfc_cliente, folio_nota)
                
                # Registrar métrica de éxito
                put_metric('NotificationsSent', 1, dimensions=[
                    {'Name': 'Environment', 'Value': ENVIRONMENT},
                    {'Name': 'Status', 'Value': 'Success'}
                ])
            else:
                error_count += 1
                put_metric('NotificationErrors', 1, dimensions=[
                    {'Name': 'Environment', 'Value': ENVIRONMENT},
                    {'Name': 'ErrorType', 'Value': 'SendFailed'}
                ])
                
        except Exception as e:
            logger.error(f"Error processing record: {e}")
            error_count += 1
            put_metric('NotificationErrors', 1, dimensions=[
                {'Name': 'Environment', 'Value': ENVIRONMENT},
                {'Name': 'ErrorType', 'Value': 'ProcessingError'}
            ])
    
    # Calcular duración
    duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    # Registrar métrica de tiempo de ejecución
    put_metric('NotificationProcessingTime', duration_ms, 'Milliseconds')
    
    # Respuesta
    response = {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Processing complete',
            'success_count': success_count,
            'error_count': error_count,
            'duration_ms': duration_ms,
            'environment': ENVIRONMENT
        })
    }
    
    logger.info(f"Lambda execution complete: {response}")
    return response


# Para testing local
if __name__ == "__main__":
    # Evento de prueba
    test_event = {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps({
                        "cliente_email": "test@example.com",
                        "cliente_nombre": "Test Cliente",
                        "folio_nota": "NV-000001",
                        "rfc_cliente": "TEST123456ABC",
                        "download_url": "http://localhost:8001/notas/TEST123456ABC/NV-000001/descargar"
                    })
                }
            }
        ]
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
