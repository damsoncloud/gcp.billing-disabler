# Provided by devenv's `image_build` from the Python and uv versions it uses, so the image matches the development environment
ARG PYTHON_VERSION
ARG UV_VERSION
ARG VENV=/opt/venv

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM docker.io/library/python:${PYTHON_VERSION}-slim AS build
ARG VENV

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=${VENV} \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /src

# Dependencies are installed before the project is copied, so the layer is reused while only the code changes
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src/ src/
RUN uv sync --locked --no-dev --no-editable

FROM docker.io/library/python:${PYTHON_VERSION}-slim
ARG VENV
ARG APP_UID=10001
ARG VERSION
ARG REVISION

LABEL org.opencontainers.image.source="https://github.com/damsoncloud/gcp.billing-disabler" \
      org.opencontainers.image.description="Event-driven disabling of GCP project billing on exceeded budgets" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"

ENV PATH="${VENV}/bin:$PATH" \
    PORT=8080 \
    PYTHONUNBUFFERED=1 \
    FUNCTION_TARGET=handle_budget_notification \
    FUNCTION_SOURCE=/opt/main.py

COPY --from=build ${VENV} ${VENV}

# functions-framework accepts only a file path, so link the installed module to a stable location
RUN ln -s "$(python -c 'import importlib.util; print(importlib.util.find_spec("billing_disabler.main").origin)')" "$FUNCTION_SOURCE"

RUN useradd --no-create-home --shell /usr/sbin/nologin --uid "$APP_UID" billing-disabler
USER ${APP_UID}

EXPOSE ${PORT}

CMD ["functions-framework"]
