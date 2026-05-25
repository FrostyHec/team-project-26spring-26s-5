#!/usr/bin/env sh
set -eu

if [ "$(id -u)" = "0" ]; then
  data_path="${DATA_PATH:-/data}"
  db_path="${DB_PATH:-$data_path}"

  mkdir -p "$data_path"
  chown -R app:app "$data_path"

  if [ "$db_path" != ":memory:" ]; then
    mkdir -p "$db_path"
    chown -R app:app "$db_path"
  fi

  exec gosu app "$@"
fi

exec "$@"
