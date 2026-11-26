FROM docker.io/evoapicloud/evolution-api:v2.3.7 AS build
USER root
WORKDIR /evolution
RUN apk add --no-cache git
# Exact source revision for upstream release 2.3.7.
RUN git init /tmp/evolution-source && \
    git -C /tmp/evolution-source remote add origin https://github.com/evolution-foundation/evolution-api.git && \
    git -C /tmp/evolution-source fetch --depth=1 origin cd800f2976e1e5b682fbf86a01ee4d85ae61f370 && \
    git -C /tmp/evolution-source checkout --detach FETCH_HEAD && \
    cp -a /tmp/evolution-source/src /evolution/ && \
    cp /tmp/evolution-source/tsconfig.json /tmp/evolution-source/tsup.config.ts /evolution/
COPY patch.cjs zenit-history.ts /tmp/zenit/
RUN node /tmp/zenit/patch.cjs /evolution && npm run build
FROM docker.io/evoapicloud/evolution-api:v2.3.7
WORKDIR /evolution
COPY --from=build /evolution/dist /evolution/dist
