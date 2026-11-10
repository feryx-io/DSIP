#!/usr/bin/env bash
# DSIP WAN testbed — base config for one host. Idempotent.
#
#   ROLE=hints|bootstrap|dht|relay|mailbox|turn|stun|endpoint   (comma-separate to combine, e.g. ROLE=hints,relay)
#   PUBLIC_IP=<this host's public v4>       (auto-detected if unset)
#   DSIP_RS_REF=<branch|tag|commit>         (of dsip-rs, where the binaries come from; default main; pin one commit
#                                            for a whole campaign — every host the same)
#   PREBUILT=<dir>                          (optional: install binaries from here instead of building; see README §1)
#   DHT_SEED=<32-byte hex>                  (optional: fixed PeerId so bootstrap addrs survive restarts)
#   BOOTSTRAP=<multiaddr>[,<multiaddr>]     (required for ROLE=dht; omit for the bootstrap node itself)
#   DEBS=<dir>                              (ROLE=relay,mailbox: dsip-rs's packages and the client: dsip-relay_*.deb,
#                                            dsip-mailbox_*.deb, dsip-node_*.deb, dsip-web-*.tar.gz, and its
#                                            packaging/one-host/configure, which sets them up (README §1); with
#                                            ROLE=hints, the dsip-node .deb from here is installed too)
#   RELAY_HOST=<dns name>                   (ROLE=relay,mailbox: the one name of the relay, the client and the mailbox)
#   RELAY_CERT=<dir>/fullchain.pem          (optional: its certificate, e.g. Let's Encrypt's /etc/letsencrypt/live/<name>/,
#                                            privkey.pem beside it; renewals reach both services by configure's deploy
#                                            hook. Without it: a self-signed certificate in $STATE/tls)
#   RELAY_WWW=<dir>                          (optional: the browser client already unpacked there; by default the
#                                            dsip-web tarball in DEBS, unpacked to /usr/local/share/dsip-web)
#   CLIENT_NODES=<https url>[,<url>]         (optional: hints nodes for the client's defaults after this origin's own)
#   TURN_URI=turn:<L4>:3478                  (optional: the relay mints TURN credentials at /turn from $STATE/turn.secret,
#                                            the secret L4's coturn holds)
#   MAILBOX_OWNER=<did>[,<did>]             (ROLE=mailbox: identities this mailbox serves; and/or MAILBOX_SERVE_ANY)
#   MAILBOX_SERVE_ANY=<n>                   (ROLE=mailbox: serve up to n identities that enrol by binding, spec-gap 115:
#                                            the browser client's did:key identities; /config.json advertises the
#                                            mailbox to them as "mailbox": {"uri", "did"})
#   MAILBOX_RELEASE_IDLE=0                  (ROLE=mailbox with MAILBOX_SERVE_ANY: keep enrolments forever; by default the
#                                            mailbox runs --release-idle and ends the enrolment of an identity none of
#                                            whose devices has connected within --mls-retention, freeing its place in
#                                            --serve-any; MAILBOX_OWNER identities never expire; M§4.1, spec-gap 130)
#   MAILBOX_DOCS="alice bob"                (names under /var/lib/dsip/docs/<name>.json the mailbox resolves from)
#   HINTS_PEERS=<host>[,<host>]             (ROLE=hints: your other hints nodes. Each is an overlay bootstrap node, its
#                                            PeerId read from http://<host>:8090/dsip/v1/node (or give the multiaddr
#                                            /ip4/<ip>/tcp/4610/p2p/<PeerId>), and <host>:6881 a Mainline bootstrap node,
#                                            with dht.libtorrent.org:25401 and relay.pkarr.org:6881 after them. Omit on
#                                            the first node; give it to each later one: they find the others from there)
#   HINTS_HTTP=<addr:port>                  (ROLE=hints: the HTTP hints API, default 0.0.0.0:8090, served directly to
#                                            other nodes and clients (profile §10); the relay's /dsip/v1/ proxy and the
#                                            mailbox use 127.0.0.1:8090 either way, so 127.0.0.1:8090 keeps it local)
#   TURN_SECRET=<string>                    (ROLE=turn: the TURN REST API secret, default: generated into $STATE/turn.secret;
#                                            credentials are minted from it: `dsipctl turn-cred` or the relay's /turn)
#
# Example:
#   ROLE=hints,relay ./node-setup.sh                                            # the first hints node
#   ROLE=hints,relay HINTS_PEERS=45.33.102.196 ./node-setup.sh                  # each later one: any running node
#   DEBS=/root/debs ROLE=bootstrap,hints,relay,mailbox RELAY_HOST=<L1 name> MAILBOX_OWNER=did:web:alice.example \
#     DHT_SEED=$(openssl rand -hex 32) ./node-setup.sh                                                          # L1
#   DEBS=/root/debs ROLE=dht,hints,relay,mailbox RELAY_HOST=<L2 name> MAILBOX_OWNER=did:web:bob.example \
#     HINTS_PEERS=<L1> BOOTSTRAP=/ip4/1.2.3.4/tcp/4001/p2p/12D3... ./node-setup.sh                              # L2
#   ROLE=dht        BOOTSTRAP=... ./node-setup.sh                               # L3
#   ROLE=dht,turn   BOOTSTRAP=... ./node-setup.sh                               # L4 (coturn: STUN and TURN)
#   ROLE=endpoint ./node-setup.sh                                               # NAT'd box (no daemons)
set -euo pipefail
ROLE=${ROLE:?set ROLE}
PUBLIC_IP=${PUBLIC_IP:-$(curl -4 -s https://ifconfig.me || hostname -I | awk '{print $1}')}
DSIP_RS_REF=${DSIP_RS_REF:-main}
SRC=/opt/dsip-rs-src; BIN=/usr/local/bin; STATE=/var/lib/dsip; LOG=/var/log/dsip
DHT_PORT=4001; RELAY_PORT=8443; MAILBOX_PORT=9443
BINS="dsip dsip-dht-node dsip-msg dsip-node"   # the relay and the mailbox: the packages (DEBS)
HINTS_HTTP=${HINTS_HTTP:-0.0.0.0:8090}
has(){ [[ ",$ROLE," == *",$1,"* ]]; }

echo "== $(hostname) role=$ROLE public=$PUBLIC_IP ref=$DSIP_RS_REF"

# ---- packages ----------------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q git curl python3 python3-numpy ffmpeg espeak-ng tcpdump netcat-openbsd jq iproute2 chrony \
  moreutils openssl
if has stun || has turn; then apt-get install -y -q coturn; fi
systemctl enable --now chrony   # envelope replay window is 300 s; clocks must agree
mkdir -p $STATE $LOG $STATE/docs

# ---- binaries: prebuilt, or build here ---------------------------------------
if [ -n "${PREBUILT:-}" ]; then
  # a set prebuilt before the hints role has no dsip-node: only ROLE=hints needs it (checked there)
  for b in $BINS; do [ -f "$PREBUILT/$b" ] && install -m755 "$PREBUILT/$b" $BIN/$b; done
  [ -f "$PREBUILT/dsip-node.service" ] && cp "$PREBUILT/dsip-node.service" $STATE/dsip-node.service
  [ -f "$PREBUILT/COMMIT" ] && cp "$PREBUILT/COMMIT" $STATE/commit
else
  # perl + make: forge-media vendors OpenSSL. The toolchain itself comes from dsip-rs's rust-toolchain.toml
  # (rustup installs the pinned channel on the first cargo run there).
  apt-get install -y -q build-essential pkg-config libssl-dev cmake clang perl make
  if ! command -v cargo >/dev/null && [ ! -x "$HOME/.cargo/bin/cargo" ]; then
    curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain none
  fi
  source "$HOME/.cargo/env"
  # the Rust implementation lives in dsip-rs; its spec/ submodule (DSIP at a tag) holds the schemas it embeds
  if [ -d $SRC/.git ]; then git -C $SRC fetch -q --tags origin; else git clone -q https://github.com/feryx-io/dsip-rs.git $SRC; fi
  git -C $SRC checkout -q "$DSIP_RS_REF"
  # a branch follows its remote; a tag or a commit stays where it is
  if git -C $SRC symbolic-ref -q HEAD >/dev/null; then git -C $SRC merge -q --ff-only "origin/$DSIP_RS_REF"; fi
  git -C $SRC submodule update -q --init
  git -C $SRC rev-parse HEAD > $STATE/commit
  # A release build of the whole set wants ~3 GB of RAM and ~6 GB of disk: build on a 4 GB host (or the
  # endpoint box) and hand the result to the small ones with PREBUILT.
  ( cd $SRC && cargo build -q --release -p dsip-cli -p dsip-dht -p dsip-mailbox -p dsip-node )   # dsip-msg: dsip-mailbox's
  mkdir -p $STATE/prebuilt
  for b in $BINS; do
    install -m755 $SRC/target/release/$b $BIN/$b
    install -m755 $SRC/target/release/$b $STATE/prebuilt/$b
  done
  cp $SRC/crates/dsip-node/packaging/debian/dsip-node.service $STATE/dsip-node.service
  cp $STATE/dsip-node.service $STATE/prebuilt/
  cp $STATE/commit $STATE/prebuilt/COMMIT
  echo "Prebuilt set for the other hosts: $STATE/prebuilt  (scp -r it, then PREBUILT=<dir> ./node-setup.sh)"
fi
echo "PUBLIC_IP=$PUBLIC_IP" > $STATE/env
echo "commit: $(cat $STATE/commit 2>/dev/null || echo unknown)"

# ---- hints node (dsip-node: the overlay, Mainline/Pkarr, the HTTP hints API) --
# The relay's /dsip/v1/ proxy and the mailbox's --hints-node reach it at 127.0.0.1:8090. Open 4610/tcp and 6881/udp
# (and 8090/tcp when HINTS_HTTP is public).
if has hints; then
  if [ -n "${DEBS:-}" ] && ls "$DEBS"/dsip-node_*_"$(dpkg --print-architecture)".deb >/dev/null 2>&1; then
    apt-get install -y -q "$DEBS"/dsip-node_*_"$(dpkg --print-architecture)".deb
  fi
  # the .deb's binary and unit when it is installed; otherwise ours, with the packaged unit's sandbox
  if [ -x /usr/bin/dsip-node ] && [ -f /usr/lib/systemd/system/dsip-node.service ]; then
    rm -f /etc/systemd/system/dsip-node.service
  else
    [ -x $BIN/dsip-node ] || { echo "ROLE=hints needs dsip-node: rebuild, or a PREBUILT set that has it" >&2; exit 1; }
    [ -f $STATE/dsip-node.service ] || { echo "ROLE=hints needs dsip-node.service (built with dsip-node)" >&2; exit 1; }
    sed "s#^ExecStart=/usr/bin/dsip-node#ExecStart=$BIN/dsip-node#" $STATE/dsip-node.service > /etc/systemd/system/dsip-node.service
  fi
  # The overlay's bootstrap needs each peer's PeerId: its HTTP API says. Mainline's needs only the host. A Mainline
  # list REPLACES the library's public nodes, so a public node that answers goes after ours (2026-10-16: L3, with
  # one stale saved node and router.bittorrent.com silent, could not rejoin until its peers were listed).
  OVERLAY=""; MAINLINE=""
  for p in ${HINTS_PEERS:+${HINTS_PEERS//,/ }}; do
    if [[ $p == /* ]]; then
      addr=$p; host=$(echo "$p" | cut -d/ -f3)
    else
      host=$p
      id=$(curl -sf --max-time 5 "http://$host:8090/dsip/v1/node" | jq -r .peer_id || true)
      if [ -z "$id" ] || [ "$id" = null ]; then
        echo "!! $host: no PeerId at http://$host:8090/dsip/v1/node — Mainline only; give its multiaddr for the overlay" >&2
        MAINLINE="$MAINLINE\"$host:6881\", "; continue
      fi
      if [[ $host =~ ^[0-9.]+$ ]]; then addr="/ip4/$host/tcp/4610/p2p/$id"; else addr="/dns4/$host/tcp/4610/p2p/$id"; fi
    fi
    OVERLAY="$OVERLAY\"$addr\", "; MAINLINE="$MAINLINE\"$host:6881\", "
  done
  MAINLINE="$MAINLINE\"dht.libtorrent.org:25401\", \"relay.pkarr.org:6881\""
  # the co-located relay connects over loopback and names its client; the node honours that from loopback only
  TRUST=false; has relay && TRUST=true
  mkdir -p /etc/dsip-node
  cat > /etc/dsip-node/config.toml.new <<CONF
# dsip-node, written by node-setup.sh (ROLE=hints). Every key: /usr/share/doc/dsip-node/config.example.toml, or
# dsip-rs crates/dsip-node/config.example.toml. A hints node is never authoritative (DSIP core §8.1).
[node]
state_dir = "/var/lib/dsip-node"

[overlay]
listen = ["/ip4/0.0.0.0/tcp/4610"]
bootstrap = [${OVERLAY%, }]

[mainline]
enabled = true
port = 6881
server = true
bootstrap = [$MAINLINE]

[http]
listen = "$HINTS_HTTP"

[limits]
ban_secs = 600
ban_ip = false
http_requests_per_ip_per_min = 120
trust_x_forwarded_for = $TRUST
CONF
  if [ -f /etc/dsip-node/config.toml ] && ! cmp -s /etc/dsip-node/config.toml /etc/dsip-node/config.toml.new; then
    cp /etc/dsip-node/config.toml /etc/dsip-node/config.toml.bak-$(date +%Y%m%d%H%M%S)
  fi
  mv /etc/dsip-node/config.toml.new /etc/dsip-node/config.toml
  systemctl daemon-reload; systemctl enable dsip-node; systemctl restart dsip-node
  for _ in $(seq 30); do NODE=$(curl -sf http://127.0.0.1:${HINTS_HTTP##*:}/dsip/v1/node) && break; sleep 1; done
  [ -n "${NODE:-}" ] || { echo "!! dsip-node did not come up: journalctl -u dsip-node" >&2; exit 1; }
  sleep 5   # a moment to dial the bootstrap nodes
  NODE=$(curl -sf http://127.0.0.1:${HINTS_HTTP##*:}/dsip/v1/node)
  echo "Hints node:   /ip4/$PUBLIC_IP/tcp/4610/p2p/$(echo "$NODE" | jq -r .peer_id)   (HINTS_PEERS=$PUBLIC_IP for the next one)"
  echo "              overlay peers $(echo "$NODE" | jq .overlay.peers), records $(echo "$NODE" | jq .overlay.records); HTTP $HINTS_HTTP"
fi

# ---- DHT node (bootstrap or member) ------------------------------------------
if has bootstrap || has dht; then
  SEEDARG=""
  if [ -n "${DHT_SEED:-}" ]; then echo "$DHT_SEED" > $STATE/dht.seed; fi
  [ -f $STATE/dht.seed ] && SEEDARG="--seed $(cat $STATE/dht.seed)"
  BOOTARG=""
  if [ -n "${BOOTSTRAP:-}" ]; then
    echo "$BOOTSTRAP" > $STATE/bootstrap
    for b in ${BOOTSTRAP//,/ }; do BOOTARG="$BOOTARG --bootstrap $b"; done
  fi
  : > $LOG/dht.log   # the PeerId is read from the first `peer:` line below: never an earlier run's
  cat > /etc/systemd/system/dsip-dht.service <<UNIT
[Unit]
Description=DSIP reachability-hints DHT node
After=network-online.target chrony.service
[Service]
ExecStart=$BIN/dsip-dht-node --listen /ip4/0.0.0.0/tcp/$DHT_PORT --control 127.0.0.1:4101 --republish 60 --peers-file $STATE/dht.peers $SEEDARG $BOOTARG
Restart=always
StandardOutput=append:$LOG/dht.log
StandardError=append:$LOG/dht.log
[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload; systemctl enable dsip-dht; systemctl restart dsip-dht
  sleep 2
  # Compose the shareable bootstrap multiaddr from the KNOWN public IP + listen port + PeerId.
  # Do NOT grep the node's own `listening:` lines and rewrite 0.0.0.0: libp2p expands the wildcard
  # into one NewListenAddr per interface (loopback + any docker/private bridges, loopback often
  # FIRST) and never emits a literal 0.0.0.0 line — so a first-match + s#0.0.0.0# rewrite yields an
  # unreachable 127.0.0.1 bootstrap addr. The PeerId is stable (pinned by DHT_SEED when set); the
  # public IP and port are known here, so build the addr ourselves.
  PEER=$(grep -m1 '^peer: ' $LOG/dht.log | cut -d' ' -f2)
  if [ -z "$PEER" ]; then echo "!! could not read PeerId from $LOG/dht.log — is dsip-dht up?" >&2; exit 1; fi
  ADDR="/ip4/$PUBLIC_IP/tcp/$DHT_PORT/p2p/$PEER"
  echo "$ADDR" > $STATE/my-multiaddr
  echo "DHT multiaddr (give this to other nodes as --bootstrap):"; echo "   $ADDR"
fi

# ---- relay + mailbox: the packages, one host, one name ------------------------------------------------------------
# dsip-rs's .debs, set up by its packaging/one-host/configure (dsip-rs docs/one-host.md): the relay serving the client,
# its defaults, TURN credentials and the local hints node at /dsip/v1/; the mailbox under the same certificate.
if has relay || has mailbox; then
  # one host: the relay, the mailbox and the hints node in front of which the relay sits (ROLE=hints now, or before)
  { has relay && has mailbox; } || { echo "ROLE: relay and mailbox come together (one host)" >&2; exit 1; }
  { has hints || dpkg -s dsip-node >/dev/null 2>&1; } || { echo "ROLE=relay,mailbox needs the hints node: add hints" >&2; exit 1; }
  [ -n "${DEBS:-}" ] || { echo "ROLE=relay,mailbox needs DEBS=<dir> (README §1: the packages, the client, configure)" >&2; exit 1; }
  NAME=${RELAY_HOST:?ROLE=relay,mailbox needs RELAY_HOST=<dns name>}
  ARCH=$(dpkg --print-architecture)
  [ -x "$DEBS/configure" ] || { echo "no $DEBS/configure (dsip-rs packaging/one-host/configure)" >&2; exit 1; }
  [ -n "${MAILBOX_OWNER:-}${MAILBOX_SERVE_ANY:-}" ] || { echo "ROLE=mailbox needs MAILBOX_OWNER=<did> and/or MAILBOX_SERVE_ANY=<n>"; exit 1; }
  # The services as node-setup.sh ran them before the packages: units in /etc/systemd/system (which would override
  # the packages'), binaries in /usr/local/bin (ahead of /usr/bin on PATH), state in $STATE/<svc>. Their state moves
  # into the packages' state directories, once, after a backup in /root/pb.
  MIGRATE=""
  for svc in relay mailbox; do
    unit=/etc/systemd/system/dsip-$svc.service
    if [ -f $unit ] && grep -q "^ExecStart=$BIN/dsip-$svc" $unit; then
      systemctl stop dsip-$svc
      mkdir -p /root/pb; stamp=$(date +%Y%m%d%H%M%S)
      tar -czf /root/pb/dsip-$svc-before-packages-$stamp.tar.gz -C / "${STATE#/}/$svc" "${unit#/}" "${BIN#/}/dsip-$svc"
      echo "backed up $STATE/$svc, $unit and $BIN/dsip-$svc in /root/pb/dsip-$svc-before-packages-$stamp.tar.gz"
      rm -f $unit $BIN/dsip-$svc; MIGRATE="$MIGRATE $svc"
    fi
  done
  systemctl daemon-reload
  apt-get install -y -q "$DEBS"/dsip-relay_*_"$ARCH".deb "$DEBS"/dsip-mailbox_*_"$ARCH".deb
  for svc in $MIGRATE; do
    # the package started its service on a new, empty state: the old state takes its place (systemd hands the tree to
    # the service's DynamicUser when it starts; a mailbox's JSON state is imported into mailbox.sqlite once)
    systemctl stop dsip-$svc
    rm -rf /var/lib/private/dsip-$svc; install -d -m 0700 /var/lib/private
    cp -a $STATE/$svc /var/lib/private/dsip-$svc; chmod 0700 /var/lib/private/dsip-$svc
    mv $STATE/$svc $STATE/$svc.moved-to-packages
    echo "moved $STATE/$svc to /var/lib/private/dsip-$svc (the old copy: $STATE/$svc.moved-to-packages)"
  done
  # the restarting hook of before; configure's own hook reloads both services instead
  rm -f /etc/letsencrypt/renewal-hooks/deploy/dsip-relay.sh
  WWW=${RELAY_WWW:-}
  if [ -z "$WWW" ]; then
    WWW=/usr/local/share/dsip-web
    rm -rf $WWW.new; mkdir -p $WWW.new
    tar -xzf "$(ls "$DEBS"/dsip-web-*.tar.gz | tail -1)" --strip-components 1 -C $WWW.new
    if [ -d $WWW ] && ! diff -rq $WWW $WWW.new >/dev/null; then rm -rf $WWW.old; mv $WWW $WWW.old; fi
    rm -rf $WWW; mv $WWW.new $WWW
  fi
  if [ -n "${RELAY_CERT:-}" ]; then
    CERT_DIR=$(dirname "$RELAY_CERT")
  else
    # no certificate: one self-signed for the name, which endpoints then need in their CA bundle
    CERT_DIR=$STATE/tls
    if [ ! -f $CERT_DIR/fullchain.pem ]; then
      mkdir -p $CERT_DIR
      openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 3650 -subj "/CN=$NAME" \
        -addext "subjectAltName = DNS:$NAME,IP:$PUBLIC_IP" -keyout $CERT_DIR/privkey.pem -out $CERT_DIR/fullchain.pem 2>/dev/null
    fi
  fi
  ARGS=(--name "$NAME" --cert-dir "$CERT_DIR" --www "$WWW" --port "$RELAY_PORT" --mailbox-port "$MAILBOX_PORT" --host "$PUBLIC_IP")
  for o in ${MAILBOX_OWNER:+${MAILBOX_OWNER//,/ }}; do ARGS+=(--owner "$o"); done
  if [ -n "${MAILBOX_SERVE_ANY:-}" ]; then
    ARGS+=(--serve-any "$MAILBOX_SERVE_ANY")
    # an idle enrolment ends and frees its --serve-any place (M§4.1 idle expiry, spec-gap 130)
    [ "${MAILBOX_RELEASE_IDLE:-1}" = 0 ] || ARGS+=(--release-idle)
  fi
  for n in ${MAILBOX_DOCS:-alice bob}; do [ -f $STATE/docs/$n.json ] && ARGS+=(--resolver-file $STATE/docs/$n.json); done
  [ ! -f $STATE/ca-all.pem ] || ARGS+=(--peers-ca $STATE/ca-all.pem)
  for u in ${CLIENT_NODES:+${CLIENT_NODES//,/ }}; do ARGS+=(--client-node "$u"); done
  if [ -n "${TURN_URI:-}" ]; then
    [ -f $STATE/turn.secret ] || { echo "TURN_URI needs $STATE/turn.secret (the secret coturn holds)"; exit 1; }
    ARGS+=(--turn-uri "$TURN_URI" --turn-secret-file $STATE/turn.secret)
  fi
  "$DEBS/configure" "${ARGS[@]}"
  [ -n "${RELAY_CERT:-}" ] || echo "Relay and mailbox certificate (self-signed: into every endpoint's CA bundle): $CERT_DIR/fullchain.pem"
fi

# ---- STUN / TURN (coturn) ------------------------------------------------------
if has stun || has turn; then
  {
    # Bind to the public address itself, not 0.0.0.0: with a wildcard, coturn maps its own external address back
    # to the wildcard and refuses it as a peer (403 Forbidden IP), so two relay-only clients of this server could
    # never reach each other. (Assumes PUBLIC_IP is on an interface, as on a Linode; behind 1:1 NAT keep 0.0.0.0.)
    echo "listening-port=3478"; echo "listening-ip=$PUBLIC_IP"; echo "relay-ip=$PUBLIC_IP"; echo "external-ip=$PUBLIC_IP"
    echo "fingerprint"; echo "no-cli"; echo "no-tls"; echo "no-dtls"
    # coturn runs as user turnserver, which cannot create files in /var/log itself
    mkdir -p /var/log/turnserver; chown turnserver:turnserver /var/log/turnserver 2>/dev/null || true
    echo "log-file=/var/log/turnserver/turn.log"; echo "simple-log"
    # Two relay-only clients on this server are each other's peer at this server's own address
    echo "allowed-peer-ip=$PUBLIC_IP"
    if has turn; then
      # TURN REST API credentials (coturn `use-auth-secret`): a client's username is `<expiry>:<name>` and its
      # password HMAC-SHA1(secret, username), minted by the relay at /turn for browsers and by `dsipctl turn-cred`
      # for the CLI. coturn allows one mechanism at a time, so static users are gone with this.
      TURN_SECRET=${TURN_SECRET:-$(cat $STATE/turn.secret 2>/dev/null || openssl rand -hex 24)}
      (umask 077; echo "$TURN_SECRET" > $STATE/turn.secret)
      echo "use-auth-secret"; echo "static-auth-secret=$TURN_SECRET"; echo "realm=dsip.test"
      echo "min-port=49160"; echo "max-port=49200"    # open this UDP range in the cloud firewall
    else
      echo "stun-only"
    fi
  } > /etc/turnserver.conf
  sed -i 's/^#TURNSERVER_ENABLED=1/TURNSERVER_ENABLED=1/' /etc/default/coturn 2>/dev/null || true
  systemctl enable coturn; systemctl restart coturn
  echo "STUN: $PUBLIC_IP:3478"
  if has turn; then echo "TURN: turn:$PUBLIC_IP:3478  secret in $STATE/turn.secret (copy it to the relay hosts; credentials: dsipctl turn-cred)   (relay ports 49160-49200/udp)"; fi
fi

# ---- endpoint: identity dirs only --------------------------------------------
if has endpoint; then
  mkdir -p $STATE/ids
  for n in alice bob; do
    [ -d $STATE/ids/$n ] || dsip identity init --dir $STATE/ids/$n --name ${n^}
    echo "$n: $(jq -r .identity $STATE/ids/$n/identity.json)"
  done
fi

echo "== done. logs in $LOG; state in $STATE"
