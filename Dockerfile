# Dockerfile para Lambda de Notificaciones
FROM public.ecr.aws/lambda/python:3.11

# Copiar requirements e instalar dependencias
COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# Copiar código fuente
COPY src/ ${LAMBDA_TASK_ROOT}/

# Establecer el handler
CMD [ "handler.lambda_handler" ]
