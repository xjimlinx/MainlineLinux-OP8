#!/usr/bin/env bash
set -euo pipefail
op8_project=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$op8_project/sources.env"
mkdir -p "$op8_project"/{downloads,sources,configs,build,artifacts,logs,toolchains}

op8_space_check() {
    local avail
    avail=$(df --output=avail -B1 "$op8_project" | tail -1)
    if (( avail < ${1:-21474836480} )); then
        echo 'Insufficient free space; stopping without deleting any files.' >&2
        return 1
    fi
}

op8_curl_direct() {
    env -u http_proxy -u https_proxy -u all_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
        curl --fail --location --connect-timeout 15 --max-time 1800 --retry 3 \
        --retry-delay 3 --speed-limit 1024 --speed-time 90 "$@"
}

op8_fetch() {
    local url=$1 dest=$2
    if [[ -s "$dest" ]]; then return 0; fi
    case "$url" in
        https://mirrors.tuna.tsinghua.edu.cn/*)
            op8_curl_direct --output "$dest.part" "$url" ;;
        *)
            if ! curl --fail --location --connect-timeout 15 --max-time 1800 --retry 2 \
                --speed-limit 1024 --speed-time 90 --output "$dest.part" "$url"; then
                echo 'Proxy/default route failed; trying direct HTTPS without disabling certificate checks.' >&2
                op8_curl_direct --output "$dest.part" "$url"
            fi ;;
    esac
    mv -- "$dest.part" "$dest"
}
