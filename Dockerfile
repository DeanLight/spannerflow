FROM lukemathwalker/cargo-chef:latest-rust-alpine AS chef
WORKDIR /app

FROM chef AS planner
COPY ./Cargo.toml ./Cargo.lock ./
COPY ./src ./src
RUN cargo chef prepare

FROM chef AS builder
COPY --from=planner /app/recipe.json .
RUN cargo chef cook --release
RUN apk update && apk add --no-cache make protobuf-dev
COPY . .
RUN cargo build --release
RUN mv ./target/release/spannerflow ./app

FROM scratch AS runtime
WORKDIR /app
COPY --from=builder /app/app /usr/local/bin/
EXPOSE 50051
ENV BIND_IP=0.0.0.0
ENTRYPOINT ["/usr/local/bin/app"]