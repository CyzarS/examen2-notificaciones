# Lambda de Notificaciones

Función Lambda que procesa mensajes de SNS y envía notificaciones por correo electrónico usando AWS SES.

## Arquitectura

```
SNS Topic → Lambda → SES → Cliente
                ↓
              S3 (actualiza metadatos)
```

## Funcionalidades

- Escucha mensajes del topic SNS de notas de venta
- Envía correos HTML profesionales usando SES
- Actualiza metadatos en S3 (hora-envio, veces-enviado)
- Registra métricas en CloudWatch

## Métricas CloudWatch

- **NotificationsSent**: Conteo de notificaciones enviadas exitosamente
- **NotificationErrors**: Conteo de errores por tipo
- **NotificationProcessingTime**: Tiempo de procesamiento en ms

## Estructura del Mensaje SNS

```json
{
  "cliente_email": "cliente@example.com",
  "cliente_nombre": "Nombre del Cliente",
  "folio_nota": "NV-000001",
  "rfc_cliente": "RFC123456ABC",
  "download_url": "https://api.example.com/notas/RFC/FOLIO/descargar"
}
```

## Configuración AWS

### Variables de Entorno Lambda
- `ENVIRONMENT`: Ambiente (local/production)
- `AWS_REGION`: Región de AWS
- `SENDER_EMAIL`: Email verificado en SES
- `S3_BUCKET`: Bucket de S3 para PDFs

### Permisos IAM Requeridos
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:CopyObject"
      ],
      "Resource": "arn:aws:s3:::bucket-name/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

## Desarrollo Local

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Ejecutar prueba local
python src/handler.py
```

## Docker

```bash
docker build -t notificaciones-lambda .
docker run -p 9000:8080 \
  -e ENVIRONMENT=local \
  -e SENDER_EMAIL=test@example.com \
  notificaciones-lambda
```

## Tests

```bash
pip install pytest pytest-cov moto
pytest tests/ -v --cov=src
```

## Despliegue

El despliegue se realiza automáticamente via GitHub Actions:
1. Se ejecutan tests
2. Se construye imagen Docker
3. Se sube a ECR
4. Se actualiza la función Lambda
