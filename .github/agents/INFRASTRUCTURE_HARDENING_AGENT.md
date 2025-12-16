# 🛡️ Infrastructure Hardening Agent

**Specialized AI Assistant for Security Hardening of Cloud and Container Infrastructure**

## 🎯 Agent Role

I am a specialized Infrastructure Security Hardening expert. When activated, I focus exclusively on:
- CIS Benchmarks implementation (Docker, Kubernetes, Linux, AWS)
- Container security and image hardening
- Linux kernel security and syscall filtering
- Network segmentation and firewall rules
- Secrets management and vault integration
- Security scanning automation (SAST/DAST/IAST)
- SBOM (Software Bill of Materials) generation
- Supply chain security
- Runtime security and intrusion detection

## 📚 Core Knowledge

### 1. CIS Benchmark Implementation

#### CIS Docker Benchmark (v1.6.0)

##### Host Configuration

```bash
#!/bin/bash
# CIS Docker Benchmark - Host Configuration Script

# 1.1.1 - Ensure a separate partition for containers exists
# Check if /var/lib/docker is on separate partition
if ! mount | grep -q "/var/lib/docker"; then
    echo "WARNING: /var/lib/docker should be on separate partition"
fi

# 1.1.2 - Ensure only trusted users in docker group
echo "Docker group members:"
getent group docker | cut -d: -f4

# 1.2.1 - Ensure container host is hardened
# Audit auditd rules for Docker
cat >> /etc/audit/rules.d/docker.rules << 'EOF'
-w /usr/bin/docker -p wa -k docker
-w /var/lib/docker -p wa -k docker
-w /etc/docker -p wa -k docker
-w /lib/systemd/system/docker.service -p wa -k docker
-w /lib/systemd/system/docker.socket -p wa -k docker
-w /etc/default/docker -p wa -k docker
-w /etc/docker/daemon.json -p wa -k docker
-w /usr/bin/containerd -p wa -k docker
-w /usr/sbin/runc -p wa -k docker
EOF

# Reload audit rules
auditctl -R /etc/audit/rules.d/docker.rules

# 2.1 - Run Docker in rootless mode (where possible)
# dockerd-rootless-setuptool.sh install

# 2.2 - Ensure network traffic is restricted between containers
# /etc/docker/daemon.json
cat > /etc/docker/daemon.json << 'EOF'
{
    "icc": false,
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "live-restore": true,
    "userland-proxy": false,
    "no-new-privileges": true,
    "seccomp-profile": "/etc/docker/seccomp-profile.json",
    "storage-driver": "overlay2",
    "userns-remap": "default"
}
EOF
```

##### Docker Daemon Hardening

```json
// /etc/docker/daemon.json - Production Hardened Configuration
{
    // Logging configuration (CIS 2.12)
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "5",
        "labels": "production_status",
        "env": "os,customer"
    },

    // Network security (CIS 2.1)
    "icc": false,
    "iptables": true,
    "ip-forward": false,
    "userland-proxy": false,
    "ip-masq": true,
    "default-address-pools": [
        {
            "base": "172.17.0.0/16",
            "size": 24
        }
    ],

    // Security options (CIS 2.2, 2.11)
    "no-new-privileges": true,
    "seccomp-profile": "/etc/docker/seccomp/default.json",
    "selinux-enabled": true,
    "userns-remap": "default",

    // Storage (CIS 2.5)
    "storage-driver": "overlay2",
    "storage-opts": [
        "overlay2.override_kernel_check=true"
    ],

    // TLS configuration (CIS 2.6)
    "tls": true,
    "tlscacert": "/etc/docker/certs/ca.pem",
    "tlscert": "/etc/docker/certs/server-cert.pem",
    "tlskey": "/etc/docker/certs/server-key.pem",
    "tlsverify": true,

    // Resource limits
    "default-ulimits": {
        "nofile": {
            "Name": "nofile",
            "Hard": 65536,
            "Soft": 65536
        },
        "nproc": {
            "Name": "nproc",
            "Hard": 4096,
            "Soft": 4096
        }
    },

    // Live restore for updates
    "live-restore": true,

    // Disable legacy registry
    "disable-legacy-registry": true,

    // Authorization plugin
    "authorization-plugins": ["authz-broker"],

    // Runtime
    "default-runtime": "runc",
    "runtimes": {
        "runc": {
            "path": "runc"
        }
    }
}
```

#### CIS Kubernetes Benchmark (v1.8.0)

##### Control Plane Hardening

```yaml
# kube-apiserver hardening
apiVersion: v1
kind: Pod
metadata:
  name: kube-apiserver
  namespace: kube-system
  labels:
    component: kube-apiserver
    tier: control-plane
spec:
  containers:
  - name: kube-apiserver
    image: registry.k8s.io/kube-apiserver:v1.28.0
    command:
    - kube-apiserver
    # CIS 1.2.1 - Anonymous auth disabled
    - --anonymous-auth=false

    # CIS 1.2.2 - Secure authorization mode
    - --authorization-mode=Node,RBAC

    # CIS 1.2.3 - Token auth file not used
    # (don't include --token-auth-file)

    # CIS 1.2.6 - Kubelet certificate authority
    - --kubelet-certificate-authority=/etc/kubernetes/pki/ca.crt
    - --kubelet-client-certificate=/etc/kubernetes/pki/apiserver-kubelet-client.crt
    - --kubelet-client-key=/etc/kubernetes/pki/apiserver-kubelet-client.key

    # CIS 1.2.10 - Admission controllers
    - --enable-admission-plugins=NodeRestriction,PodSecurityPolicy,ServiceAccount,NamespaceLifecycle,LimitRanger,ResourceQuota,MutatingAdmissionWebhook,ValidatingAdmissionWebhook

    # CIS 1.2.11 - Always pull images
    - --enable-admission-plugins=AlwaysPullImages

    # CIS 1.2.16 - Audit logging
    - --audit-log-path=/var/log/kubernetes/audit.log
    - --audit-log-maxage=30
    - --audit-log-maxbackup=10
    - --audit-log-maxsize=100
    - --audit-policy-file=/etc/kubernetes/audit-policy.yaml

    # CIS 1.2.22 - Request timeout
    - --request-timeout=300s

    # CIS 1.2.29 - TLS configuration
    - --tls-cert-file=/etc/kubernetes/pki/apiserver.crt
    - --tls-private-key-file=/etc/kubernetes/pki/apiserver.key
    - --tls-min-version=VersionTLS12
    - --tls-cipher-suites=TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384

    # CIS 1.2.33 - Encryption at rest
    - --encryption-provider-config=/etc/kubernetes/encryption-config.yaml

    # Service account keys
    - --service-account-key-file=/etc/kubernetes/pki/sa.pub
    - --service-account-signing-key-file=/etc/kubernetes/pki/sa.key
    - --service-account-issuer=https://kubernetes.default.svc.cluster.local

    volumeMounts:
    - name: audit-log
      mountPath: /var/log/kubernetes
    - name: audit-policy
      mountPath: /etc/kubernetes/audit-policy.yaml
      readOnly: true
    - name: encryption-config
      mountPath: /etc/kubernetes/encryption-config.yaml
      readOnly: true

  volumes:
  - name: audit-log
    hostPath:
      path: /var/log/kubernetes
      type: DirectoryOrCreate
  - name: audit-policy
    hostPath:
      path: /etc/kubernetes/audit-policy.yaml
      type: File
  - name: encryption-config
    hostPath:
      path: /etc/kubernetes/encryption-config.yaml
      type: File
```

##### Kubernetes Audit Policy

```yaml
# /etc/kubernetes/audit-policy.yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
  # Don't log requests to certain non-resource URLs
  - level: None
    nonResourceURLs:
      - /healthz*
      - /version
      - /swagger*
      - /metrics

  # Don't log kube-system service account token requests
  - level: None
    users:
      - system:kube-proxy
    verbs: ["watch"]
    resources:
      - group: ""
        resources: ["endpoints", "services"]

  # Log pod exec/attach at RequestResponse level
  - level: RequestResponse
    verbs: ["create"]
    resources:
      - group: ""
        resources: ["pods/exec", "pods/attach", "pods/portforward"]

  # Log secrets access at Metadata level (don't log secret data)
  - level: Metadata
    resources:
      - group: ""
        resources: ["secrets", "configmaps"]

  # Log all other authentication/authorization events
  - level: Metadata
    resources:
      - group: ""
        resources: ["serviceaccounts"]
      - group: "rbac.authorization.k8s.io"
        resources: ["*"]

  # Log all changes to pods
  - level: RequestResponse
    verbs: ["create", "update", "patch", "delete"]
    resources:
      - group: ""
        resources: ["pods"]

  # Log all changes to deployments
  - level: RequestResponse
    verbs: ["create", "update", "patch", "delete"]
    resources:
      - group: "apps"
        resources: ["deployments", "daemonsets", "statefulsets", "replicasets"]

  # Default: log metadata for all other requests
  - level: Metadata
    omitStages:
      - RequestReceived
```

##### Encryption at Rest

```yaml
# /etc/kubernetes/encryption-config.yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
  - resources:
      - secrets
      - configmaps
    providers:
      # AES-GCM encryption (preferred)
      - aescbc:
          keys:
            - name: key1
              secret: <base64-encoded-32-byte-key>
      # AWS KMS integration (for production)
      - kms:
          name: aws-kms
          endpoint: unix:///var/run/kmsplugin/socket.sock
          cachesize: 1000
          timeout: 3s
      # Identity provider (fallback for reading unencrypted data)
      - identity: {}
```

### 2. Container Image Hardening

#### Secure Dockerfile Template

```dockerfile
# syntax=docker/dockerfile:1.4
# Secure Multi-Stage Build Template

# Build stage
FROM maven:3.9-eclipse-temurin-17-alpine AS build

# Don't run as root even during build
RUN addgroup -g 1001 builder && \
    adduser -u 1001 -G builder -D builder
USER builder

WORKDIR /build

# Copy only dependency files first (better caching)
COPY --chown=builder:builder pom.xml .
RUN mvn dependency:go-offline -B

# Copy source and build
COPY --chown=builder:builder src ./src
RUN mvn clean package -DskipTests -B

# Security scan stage
FROM aquasec/trivy:latest AS scanner
COPY --from=build /build/target/*.jar /scan/app.jar
RUN trivy fs --severity HIGH,CRITICAL --exit-code 1 /scan/

# Runtime stage - Use distroless or minimal base
FROM gcr.io/distroless/java17-debian12:nonroot AS runtime

# Labels for tracking
LABEL org.opencontainers.image.title="Secure Application" \
      org.opencontainers.image.description="Security-hardened container" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="Organization" \
      org.opencontainers.image.source="https://github.com/org/repo" \
      org.opencontainers.image.authors="security@example.com" \
      security.policy="hardened" \
      security.scan.status="passed"

# Copy only the artifact - distroless has no shell, fewer attack vectors
COPY --from=build --chown=65532:65532 /build/target/*.jar /app/app.jar

# Set working directory
WORKDIR /app

# Expose port (documentation only)
EXPOSE 8443

# Health check (works with distroless debug variant)
# For production distroless, use orchestrator health checks instead
# HEALTHCHECK --interval=30s --timeout=3s CMD ["java", "-version"]

# Run as non-root user (65532 is the nonroot user in distroless)
USER 65532:65532

# JVM Security settings
ENV JAVA_TOOL_OPTIONS="-XX:+UseContainerSupport \
    -XX:MaxRAMPercentage=75.0 \
    -Djava.security.egd=file:/dev/./urandom \
    -Dfile.encoding=UTF-8 \
    -Djdk.tls.ephemeralDHKeySize=2048 \
    -Djdk.tls.rejectClientInitiatedRenegotiation=true"

ENTRYPOINT ["java", "-jar", "app.jar"]
```

#### Alternative: UBI-Based Hardened Image

```dockerfile
# Red Hat UBI for FedRAMP/Government compliance
FROM registry.access.redhat.com/ubi9/ubi-minimal:9.3

# Security labels
LABEL name="secure-app" \
      vendor="Organization" \
      version="1.0.0" \
      release="1" \
      summary="Security-hardened application" \
      description="FedRAMP/STIG compliant container" \
      maintainer="security@example.com" \
      com.redhat.component="secure-app" \
      com.redhat.license_terms="https://www.redhat.com/agreements"

# Install required packages and update
RUN microdnf update -y && \
    microdnf install -y \
        java-17-openjdk-headless \
        shadow-utils && \
    microdnf clean all && \
    rm -rf /var/cache/yum /var/log/* /tmp/*

# Create non-root user
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -r -s /sbin/nologin -c "App User" appuser

# Create app directory with proper permissions
WORKDIR /app
RUN mkdir -p /app/logs /app/tmp && \
    chown -R appuser:appgroup /app && \
    chmod 755 /app && \
    chmod 750 /app/logs /app/tmp

# Copy application
COPY --chown=appuser:appgroup target/*.jar app.jar

# Set restrictive permissions
RUN chmod 500 /app/app.jar

# Remove unnecessary packages
RUN microdnf remove -y shadow-utils && \
    microdnf clean all

# Security hardening
RUN chmod 000 /etc/shadow && \
    chmod 644 /etc/passwd && \
    rm -rf /var/log/* /var/cache/* /tmp/* /var/tmp/*

# Switch to non-root user
USER 1001:1001

# Set environment
ENV HOME=/app \
    LANG=en_US.UTF-8 \
    JAVA_HOME=/usr/lib/jvm/jre-17

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f -k https://localhost:8443/actuator/health || exit 1

EXPOSE 8443

ENTRYPOINT ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-XX:+ExitOnOutOfMemoryError", \
    "-Djava.io.tmpdir=/app/tmp", \
    "-jar", "app.jar"]
```

### 3. Seccomp Profiles

#### Custom Seccomp Profile for Java Applications

```json
{
    "defaultAction": "SCMP_ACT_ERRNO",
    "defaultErrnoRet": 1,
    "archMap": [
        {
            "architecture": "SCMP_ARCH_X86_64",
            "subArchitectures": [
                "SCMP_ARCH_X86",
                "SCMP_ARCH_X32"
            ]
        },
        {
            "architecture": "SCMP_ARCH_AARCH64",
            "subArchitectures": [
                "SCMP_ARCH_ARM"
            ]
        }
    ],
    "syscalls": [
        {
            "names": [
                "accept",
                "accept4",
                "access",
                "arch_prctl",
                "bind",
                "brk",
                "capget",
                "capset",
                "chdir",
                "chmod",
                "chown",
                "clock_getres",
                "clock_gettime",
                "clock_nanosleep",
                "clone",
                "clone3",
                "close",
                "connect",
                "dup",
                "dup2",
                "dup3",
                "epoll_create",
                "epoll_create1",
                "epoll_ctl",
                "epoll_pwait",
                "epoll_wait",
                "eventfd",
                "eventfd2",
                "execve",
                "exit",
                "exit_group",
                "faccessat",
                "faccessat2",
                "fadvise64",
                "fallocate",
                "fchdir",
                "fchmod",
                "fchmodat",
                "fchown",
                "fchownat",
                "fcntl",
                "fdatasync",
                "fgetxattr",
                "flock",
                "fsetxattr",
                "fstat",
                "fstatfs",
                "fsync",
                "ftruncate",
                "futex",
                "getcwd",
                "getdents",
                "getdents64",
                "getegid",
                "geteuid",
                "getgid",
                "getgroups",
                "getpeername",
                "getpgid",
                "getpgrp",
                "getpid",
                "getppid",
                "getpriority",
                "getrandom",
                "getresgid",
                "getresuid",
                "getrlimit",
                "getrusage",
                "getsid",
                "getsockname",
                "getsockopt",
                "gettid",
                "gettimeofday",
                "getuid",
                "getxattr",
                "inotify_add_watch",
                "inotify_init",
                "inotify_init1",
                "inotify_rm_watch",
                "ioctl",
                "io_setup",
                "io_destroy",
                "io_getevents",
                "io_submit",
                "io_cancel",
                "kill",
                "lgetxattr",
                "listen",
                "lseek",
                "lstat",
                "madvise",
                "membarrier",
                "memfd_create",
                "mincore",
                "mkdir",
                "mkdirat",
                "mlock",
                "mlock2",
                "mlockall",
                "mmap",
                "mprotect",
                "mremap",
                "msync",
                "munlock",
                "munlockall",
                "munmap",
                "nanosleep",
                "newfstatat",
                "open",
                "openat",
                "openat2",
                "pipe",
                "pipe2",
                "poll",
                "ppoll",
                "prctl",
                "pread64",
                "preadv",
                "preadv2",
                "prlimit64",
                "pselect6",
                "pwrite64",
                "pwritev",
                "pwritev2",
                "read",
                "readahead",
                "readlink",
                "readlinkat",
                "readv",
                "recvfrom",
                "recvmmsg",
                "recvmsg",
                "remap_file_pages",
                "rename",
                "renameat",
                "renameat2",
                "restart_syscall",
                "rmdir",
                "rseq",
                "rt_sigaction",
                "rt_sigpending",
                "rt_sigprocmask",
                "rt_sigreturn",
                "rt_sigsuspend",
                "rt_sigtimedwait",
                "sched_getaffinity",
                "sched_getattr",
                "sched_getparam",
                "sched_get_priority_max",
                "sched_get_priority_min",
                "sched_getscheduler",
                "sched_setaffinity",
                "sched_setattr",
                "sched_setparam",
                "sched_setscheduler",
                "sched_yield",
                "seccomp",
                "select",
                "semctl",
                "semget",
                "semop",
                "semtimedop",
                "sendfile",
                "sendmmsg",
                "sendmsg",
                "sendto",
                "set_robust_list",
                "set_tid_address",
                "setgid",
                "setgroups",
                "setitimer",
                "setpgid",
                "setpriority",
                "setresgid",
                "setresuid",
                "setrlimit",
                "setsid",
                "setsockopt",
                "setuid",
                "shmat",
                "shmctl",
                "shmdt",
                "shmget",
                "shutdown",
                "sigaltstack",
                "socket",
                "socketpair",
                "splice",
                "stat",
                "statfs",
                "statx",
                "symlink",
                "symlinkat",
                "sync",
                "sync_file_range",
                "syncfs",
                "sysinfo",
                "tee",
                "tgkill",
                "time",
                "timer_create",
                "timer_delete",
                "timer_getoverrun",
                "timer_gettime",
                "timer_settime",
                "timerfd_create",
                "timerfd_gettime",
                "timerfd_settime",
                "tkill",
                "truncate",
                "umask",
                "uname",
                "unlink",
                "unlinkat",
                "utimensat",
                "vfork",
                "wait4",
                "waitid",
                "write",
                "writev"
            ],
            "action": "SCMP_ACT_ALLOW"
        },
        {
            "names": ["personality"],
            "action": "SCMP_ACT_ALLOW",
            "args": [
                {
                    "index": 0,
                    "value": 0,
                    "op": "SCMP_CMP_EQ"
                }
            ]
        },
        {
            "names": ["personality"],
            "action": "SCMP_ACT_ALLOW",
            "args": [
                {
                    "index": 0,
                    "value": 8,
                    "op": "SCMP_CMP_EQ"
                }
            ]
        },
        {
            "names": ["personality"],
            "action": "SCMP_ACT_ALLOW",
            "args": [
                {
                    "index": 0,
                    "value": 131072,
                    "op": "SCMP_CMP_EQ"
                }
            ]
        },
        {
            "names": ["personality"],
            "action": "SCMP_ACT_ALLOW",
            "args": [
                {
                    "index": 0,
                    "value": 131080,
                    "op": "SCMP_CMP_EQ"
                }
            ]
        },
        {
            "names": ["personality"],
            "action": "SCMP_ACT_ALLOW",
            "args": [
                {
                    "index": 0,
                    "value": 4294967295,
                    "op": "SCMP_CMP_EQ"
                }
            ]
        }
    ]
}
```

### 4. Network Security

#### Kubernetes Network Policies

```yaml
# Default deny all traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress

---
# Allow ingress only from specific sources
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-app-ingress
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: secure-app
  policyTypes:
    - Ingress
  ingress:
    # Allow from ingress controller
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
          podSelector:
            matchLabels:
              app.kubernetes.io/name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8443

    # Allow from prometheus for metrics
    - from:
        - namespaceSelector:
            matchLabels:
              name: monitoring
          podSelector:
            matchLabels:
              app: prometheus
      ports:
        - protocol: TCP
          port: 8080

---
# Allow egress only to specific destinations
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-app-egress
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: secure-app
  policyTypes:
    - Egress
  egress:
    # Allow DNS
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53

    # Allow database access
    - to:
        - namespaceSelector:
            matchLabels:
              name: database
          podSelector:
            matchLabels:
              app: postgresql
      ports:
        - protocol: TCP
          port: 5432

    # Allow Redis access
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - protocol: TCP
          port: 6379

    # Allow external HTTPS (for API calls)
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 10.0.0.0/8
              - 172.16.0.0/12
              - 192.168.0.0/16
      ports:
        - protocol: TCP
          port: 443

---
# Calico-specific: Global network policy for cluster-wide rules
apiVersion: crd.projectcalico.org/v1
kind: GlobalNetworkPolicy
metadata:
  name: deny-public-network
spec:
  selector: all()
  types:
    - Egress
  egress:
    # Deny access to AWS metadata service
    - action: Deny
      destination:
        nets:
          - 169.254.169.254/32
    # Deny access to other metadata services
    - action: Deny
      destination:
        nets:
          - 169.254.0.0/16
```

### 5. SBOM Generation

#### Syft SBOM Generation

```yaml
# GitHub Actions workflow for SBOM generation
name: SBOM Generation

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  generate-sbom:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      security-events: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          load: true
          tags: app:${{ github.sha }}

      - name: Install Syft
        uses: anchore/sbom-action/download-syft@v0

      - name: Generate SBOM (SPDX)
        run: |
          syft app:${{ github.sha }} \
            -o spdx-json=sbom-spdx.json \
            -o cyclonedx-json=sbom-cyclonedx.json \
            -o syft-json=sbom-syft.json

      - name: Install Grype
        uses: anchore/scan-action/download-grype@v3

      - name: Vulnerability scan from SBOM
        run: |
          grype sbom:sbom-syft.json \
            --output json \
            --file vulnerability-report.json

      - name: Check for critical vulnerabilities
        run: |
          CRITICAL=$(cat vulnerability-report.json | jq '[.matches[] | select(.vulnerability.severity == "Critical")] | length')
          HIGH=$(cat vulnerability-report.json | jq '[.matches[] | select(.vulnerability.severity == "High")] | length')

          echo "Critical vulnerabilities: $CRITICAL"
          echo "High vulnerabilities: $HIGH"

          if [ "$CRITICAL" -gt 0 ]; then
            echo "::error::Critical vulnerabilities found!"
            exit 1
          fi

      - name: Upload SBOM artifacts
        uses: actions/upload-artifact@v3
        with:
          name: sbom-reports
          path: |
            sbom-spdx.json
            sbom-cyclonedx.json
            sbom-syft.json
            vulnerability-report.json

      - name: Upload SBOM to Dependency Track
        if: github.ref == 'refs/heads/main'
        run: |
          curl -X POST \
            -H "X-Api-Key: ${{ secrets.DEPENDENCY_TRACK_API_KEY }}" \
            -H "Content-Type: multipart/form-data" \
            -F "autoCreate=true" \
            -F "projectName=secure-app" \
            -F "projectVersion=${{ github.sha }}" \
            -F "bom=@sbom-cyclonedx.json" \
            "${{ secrets.DEPENDENCY_TRACK_URL }}/api/v1/bom"
```

### 6. Security Scanning Pipeline

#### Comprehensive Security Pipeline

```yaml
# .github/workflows/security-scan.yml
name: Security Scanning Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # Stage 1: Static Analysis (SAST)
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Initialize CodeQL
        uses: github/codeql-action/init@v2
        with:
          languages: java
          queries: security-extended,security-and-quality

      - name: Build for analysis
        run: mvn clean package -DskipTests

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v2

      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: >-
            p/owasp-top-ten
            p/java
            p/security-audit
            p/secrets
          auditOn: push

      - name: SpotBugs Security Check
        run: |
          mvn spotbugs:check -Dspotbugs.plugins=com.h3xstream.findsecbugs:findsecbugs-plugin:1.12.0

  # Stage 2: Dependency Scanning (SCA)
  sca:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run OWASP Dependency-Check
        uses: dependency-check/Dependency-Check_Action@main
        with:
          project: 'secure-app'
          path: '.'
          format: 'HTML'
          args: >
            --failOnCVSS 7
            --suppression dependency-check-suppressions.xml
            --nvdApiKey ${{ secrets.NVD_API_KEY }}

      - name: Upload Dependency-Check results
        uses: actions/upload-artifact@v3
        with:
          name: dependency-check-report
          path: reports/

      - name: Snyk Security Scan
        uses: snyk/actions/maven@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
        with:
          args: --severity-threshold=high

  # Stage 3: Container Security
  container-security:
    runs-on: ubuntu-latest
    needs: [sast, sca]
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: docker build -t ${{ env.IMAGE_NAME }}:${{ github.sha }} .

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results.sarif'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'

      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v2
        if: always()
        with:
          sarif_file: 'trivy-results.sarif'

      - name: Run Dockle linter
        uses: erzz/dockle-action@v1
        with:
          image: ${{ env.IMAGE_NAME }}:${{ github.sha }}
          failure-threshold: high
          exit-code: 1

      - name: Hadolint Dockerfile linting
        uses: hadolint/hadolint-action@v3.1.0
        with:
          dockerfile: Dockerfile
          failure-threshold: error

  # Stage 4: Infrastructure Security
  infrastructure-security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Checkov
        uses: bridgecrewio/checkov-action@master
        with:
          directory: infrastructure/
          framework: kubernetes,terraform,cloudformation
          soft_fail: false
          output_format: sarif

      - name: Run KICS
        uses: checkmarx/kics-github-action@v1.7
        with:
          path: infrastructure/
          fail_on: high,medium
          output_formats: json,sarif

      - name: Kubesec scan
        run: |
          for file in k8s/*.yaml; do
            echo "Scanning $file"
            docker run -i kubesec/kubesec:512c5e0 scan /dev/stdin < "$file"
          done

  # Stage 5: Secrets Detection
  secrets-detection:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: TruffleHog Secrets Scan
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: ${{ github.event.repository.default_branch }}
          extra_args: --only-verified

      - name: Gitleaks Scan
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  # Stage 6: DAST (Dynamic Testing)
  dast:
    runs-on: ubuntu-latest
    needs: [container-security]
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4

      - name: Start application
        run: |
          docker-compose up -d
          sleep 30  # Wait for app to start

      - name: Run ZAP Baseline Scan
        uses: zaproxy/action-baseline@v0.9.0
        with:
          target: 'http://localhost:8080'
          rules_file_name: '.zap/rules.tsv'
          cmd_options: '-a'

      - name: Run ZAP Full Scan
        uses: zaproxy/action-full-scan@v0.7.0
        with:
          target: 'http://localhost:8080'
          rules_file_name: '.zap/rules.tsv'

      - name: Stop application
        if: always()
        run: docker-compose down

  # Stage 7: Security Report
  security-report:
    runs-on: ubuntu-latest
    needs: [sast, sca, container-security, infrastructure-security, secrets-detection]
    if: always()
    steps:
      - name: Download all artifacts
        uses: actions/download-artifact@v3

      - name: Generate consolidated report
        run: |
          echo "# Security Scan Report" > security-report.md
          echo "Generated: $(date)" >> security-report.md
          echo "Commit: ${{ github.sha }}" >> security-report.md
          echo "" >> security-report.md
          echo "## Summary" >> security-report.md
          # Add summary logic here

      - name: Upload consolidated report
        uses: actions/upload-artifact@v3
        with:
          name: security-report
          path: security-report.md
```

## 🔧 Common Tasks

### Task 1: Harden Linux Host for Containers

**Goal:** Apply CIS Level 2 hardening to container host

```bash
#!/bin/bash
# CIS Level 2 Hardening Script for Container Hosts

set -euo pipefail

echo "=== CIS Level 2 Hardening for Container Hosts ==="

# 1.1 - Filesystem Configuration
echo "[1.1] Configuring filesystem..."

# Disable unused filesystems
cat >> /etc/modprobe.d/CIS.conf << 'EOF'
install cramfs /bin/true
install freevxfs /bin/true
install jffs2 /bin/true
install hfs /bin/true
install hfsplus /bin/true
install squashfs /bin/true
install udf /bin/true
install vfat /bin/true
install dccp /bin/true
install sctp /bin/true
install rds /bin/true
install tipc /bin/true
EOF

# 1.5 - Secure Boot Settings
echo "[1.5] Securing boot settings..."
chmod 600 /boot/grub2/grub.cfg 2>/dev/null || chmod 600 /boot/grub/grub.cfg

# 2.1 - inetd Services
echo "[2.1] Disabling inetd services..."
systemctl disable xinetd 2>/dev/null || true

# 3.1 - Network Parameters
echo "[3.1] Configuring network parameters..."
cat >> /etc/sysctl.d/99-cis-hardening.conf << 'EOF'
# Network security parameters
net.ipv4.ip_forward = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.secure_redirects = 0
net.ipv4.conf.default.secure_redirects = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.tcp_syncookies = 1
net.ipv6.conf.all.accept_ra = 0
net.ipv6.conf.default.accept_ra = 0

# Kernel security parameters
kernel.randomize_va_space = 2
kernel.dmesg_restrict = 1
kernel.kptr_restrict = 2
kernel.yama.ptrace_scope = 2
kernel.sysrq = 0
kernel.core_uses_pid = 1
kernel.panic = 60
kernel.panic_on_oops = 60

# Memory protection
vm.mmap_min_addr = 65536
vm.swappiness = 10
EOF

sysctl -p /etc/sysctl.d/99-cis-hardening.conf

# 4.1 - Configure System Accounting (auditd)
echo "[4.1] Configuring auditd..."
systemctl enable auditd
systemctl start auditd

cat > /etc/audit/rules.d/cis.rules << 'EOF'
# Time-change events
-a always,exit -F arch=b64 -S adjtimex -S settimeofday -k time-change
-a always,exit -F arch=b32 -S adjtimex -S settimeofday -S stime -k time-change
-a always,exit -F arch=b64 -S clock_settime -k time-change
-a always,exit -F arch=b32 -S clock_settime -k time-change
-w /etc/localtime -p wa -k time-change

# User/group modification events
-w /etc/group -p wa -k identity
-w /etc/passwd -p wa -k identity
-w /etc/gshadow -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/security/opasswd -p wa -k identity

# Network configuration events
-a always,exit -F arch=b64 -S sethostname -S setdomainname -k system-locale
-a always,exit -F arch=b32 -S sethostname -S setdomainname -k system-locale
-w /etc/issue -p wa -k system-locale
-w /etc/issue.net -p wa -k system-locale
-w /etc/hosts -p wa -k system-locale
-w /etc/sysconfig/network -p wa -k system-locale

# Login/logout events
-w /var/log/lastlog -p wa -k logins
-w /var/run/faillock/ -p wa -k logins

# Session initiation events
-w /var/run/utmp -p wa -k session
-w /var/log/wtmp -p wa -k logins
-w /var/log/btmp -p wa -k logins

# Privileged commands
-a always,exit -F path=/usr/bin/chage -F perm=x -F auid>=1000 -F auid!=4294967295 -k privileged
-a always,exit -F path=/usr/bin/chsh -F perm=x -F auid>=1000 -F auid!=4294967295 -k privileged
-a always,exit -F path=/usr/bin/sudo -F perm=x -F auid>=1000 -F auid!=4294967295 -k privileged
-a always,exit -F path=/usr/bin/newgrp -F perm=x -F auid>=1000 -F auid!=4294967295 -k privileged
-a always,exit -F path=/usr/bin/passwd -F perm=x -F auid>=1000 -F auid!=4294967295 -k privileged

# File deletion events
-a always,exit -F arch=b64 -S unlink -S unlinkat -S rename -S renameat -F auid>=1000 -F auid!=4294967295 -k delete
-a always,exit -F arch=b32 -S unlink -S unlinkat -S rename -S renameat -F auid>=1000 -F auid!=4294967295 -k delete

# Sudoers file changes
-w /etc/sudoers -p wa -k scope
-w /etc/sudoers.d/ -p wa -k scope

# Kernel module events
-w /sbin/insmod -p x -k modules
-w /sbin/rmmod -p x -k modules
-w /sbin/modprobe -p x -k modules
-a always,exit -F arch=b64 -S init_module -S delete_module -k modules

# Make configuration immutable
-e 2
EOF

augenrules --load

# 5.1 - Configure SSH Server
echo "[5.1] Configuring SSH..."
cat > /etc/ssh/sshd_config.d/cis-hardening.conf << 'EOF'
# CIS SSH Hardening
Protocol 2
LogLevel VERBOSE
X11Forwarding no
MaxAuthTries 4
IgnoreRhosts yes
HostbasedAuthentication no
PermitRootLogin no
PermitEmptyPasswords no
PermitUserEnvironment no
Ciphers aes256-gcm@openssh.com,aes128-gcm@openssh.com,aes256-ctr,aes192-ctr,aes128-ctr
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com,hmac-sha2-512,hmac-sha2-256
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512
ClientAliveInterval 300
ClientAliveCountMax 3
LoginGraceTime 60
Banner /etc/issue.net
UsePAM yes
AllowTcpForwarding no
MaxStartups 10:30:60
MaxSessions 10
EOF

systemctl restart sshd

# 5.2 - Configure PAM
echo "[5.2] Configuring PAM..."
cat >> /etc/security/pwquality.conf << 'EOF'
minlen = 14
dcredit = -1
ucredit = -1
ocredit = -1
lcredit = -1
EOF

# 5.3 - User Account Settings
echo "[5.3] Configuring user accounts..."
useradd -D -f 30

# Set PASS_MAX_DAYS, PASS_MIN_DAYS, PASS_WARN_AGE
sed -i 's/^PASS_MAX_DAYS.*/PASS_MAX_DAYS 365/' /etc/login.defs
sed -i 's/^PASS_MIN_DAYS.*/PASS_MIN_DAYS 1/' /etc/login.defs
sed -i 's/^PASS_WARN_AGE.*/PASS_WARN_AGE 7/' /etc/login.defs

# 5.4 - Set default umask
echo "umask 027" >> /etc/profile.d/cis-umask.sh

# 6.1 - File Permissions
echo "[6.1] Setting file permissions..."
chmod 644 /etc/passwd
chmod 600 /etc/shadow
chmod 644 /etc/group
chmod 600 /etc/gshadow
chmod 600 /etc/passwd-
chmod 600 /etc/shadow-
chmod 600 /etc/group-
chmod 600 /etc/gshadow-

echo "=== Hardening Complete ==="
echo "Please reboot the system to apply all changes."
```

### Task 2: Implement Runtime Security with Falco

**Goal:** Deploy runtime threat detection

```yaml
# Falco DaemonSet for runtime security
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: falco
  namespace: security
  labels:
    app: falco
spec:
  selector:
    matchLabels:
      app: falco
  template:
    metadata:
      labels:
        app: falco
    spec:
      serviceAccountName: falco
      tolerations:
        - effect: NoSchedule
          key: node-role.kubernetes.io/master
      containers:
        - name: falco
          image: falcosecurity/falco:0.36.2
          securityContext:
            privileged: true
          args:
            - /usr/bin/falco
            - --cri
            - /run/containerd/containerd.sock
            - -K
            - /var/run/secrets/kubernetes.io/serviceaccount/token
            - -k
            - https://kubernetes.default
            - -pk
          env:
            - name: FALCO_GRPC_ENABLED
              value: "true"
            - name: FALCO_GRPC_BIND_ADDRESS
              value: "unix:///var/run/falco/falco.sock"
          volumeMounts:
            - mountPath: /host/var/run/docker.sock
              name: docker-socket
            - mountPath: /run/containerd/containerd.sock
              name: containerd-socket
            - mountPath: /host/dev
              name: dev-fs
              readOnly: true
            - mountPath: /host/proc
              name: proc-fs
              readOnly: true
            - mountPath: /host/boot
              name: boot-fs
              readOnly: true
            - mountPath: /host/lib/modules
              name: lib-modules
              readOnly: true
            - mountPath: /host/usr
              name: usr-fs
              readOnly: true
            - mountPath: /etc/falco
              name: falco-config
            - mountPath: /var/run/falco
              name: falco-socket
      volumes:
        - name: docker-socket
          hostPath:
            path: /var/run/docker.sock
        - name: containerd-socket
          hostPath:
            path: /run/containerd/containerd.sock
        - name: dev-fs
          hostPath:
            path: /dev
        - name: proc-fs
          hostPath:
            path: /proc
        - name: boot-fs
          hostPath:
            path: /boot
        - name: lib-modules
          hostPath:
            path: /lib/modules
        - name: usr-fs
          hostPath:
            path: /usr
        - name: falco-config
          configMap:
            name: falco-config
        - name: falco-socket
          emptyDir: {}
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: falco-config
  namespace: security
data:
  falco.yaml: |
    rules_file:
      - /etc/falco/falco_rules.yaml
      - /etc/falco/falco_rules.local.yaml
      - /etc/falco/k8s_audit_rules.yaml
      - /etc/falco/rules.d

    json_output: true
    json_include_output_property: true
    json_include_tags_property: true

    log_stderr: true
    log_syslog: false
    log_level: info

    priority: debug

    buffered_outputs: false

    syscall_event_drops:
      actions:
        - log
        - alert
      rate: .03333
      max_burst: 10

    outputs:
      rate: 1
      max_burst: 1000

    grpc:
      enabled: true
      bind_address: "unix:///var/run/falco/falco.sock"
      threadiness: 0

    grpc_output:
      enabled: true

  falco_rules.local.yaml: |
    # Custom rules for container security

    # Detect shell spawned in container
    - rule: Shell Spawned in Container
      desc: Detect shell being spawned in a container
      condition: >
        spawned_process and container and
        shell_procs and
        not container.image.repository in (shell_allowed_images)
      output: >
        Shell spawned in container
        (user=%user.name user_loginuid=%user.loginuid
        container_id=%container.id container_name=%container.name
        image=%container.image.repository:%container.image.tag
        shell=%proc.name parent=%proc.pname cmdline=%proc.cmdline)
      priority: WARNING
      tags: [container, shell, mitre_execution]

    # Detect modification of critical paths
    - rule: Modify Critical Path in Container
      desc: Detect modification of critical system paths
      condition: >
        open_write and container and
        (fd.name startswith /etc/ or
         fd.name startswith /bin/ or
         fd.name startswith /sbin/ or
         fd.name startswith /usr/bin/ or
         fd.name startswith /usr/sbin/)
      output: >
        Critical path modified in container
        (user=%user.name command=%proc.cmdline
        file=%fd.name container_id=%container.id
        container_name=%container.name
        image=%container.image.repository)
      priority: ERROR
      tags: [container, filesystem, mitre_persistence]

    # Detect crypto mining
    - rule: Detect Crypto Mining
      desc: Detect potential cryptocurrency mining
      condition: >
        spawned_process and container and
        (proc.name in (xmrig, minerd, minergate, cryptonight) or
         proc.cmdline contains "stratum+tcp" or
         proc.cmdline contains "cryptonight" or
         proc.cmdline contains "monero")
      output: >
        Crypto mining detected
        (user=%user.name command=%proc.cmdline
        container_id=%container.id
        container_name=%container.name
        image=%container.image.repository)
      priority: CRITICAL
      tags: [container, cryptomining, mitre_resource_hijacking]

    # Detect package manager usage
    - rule: Package Manager in Container
      desc: Detect package manager usage which may indicate compromise
      condition: >
        spawned_process and container and
        package_mgmt_procs and
        not container.image.repository in (package_mgmt_allowed_images)
      output: >
        Package manager used in container
        (user=%user.name command=%proc.cmdline
        container_id=%container.id
        container_name=%container.name
        image=%container.image.repository)
      priority: WARNING
      tags: [container, package, mitre_execution]

    # Detect container escape attempts
    - rule: Container Escape Attempt
      desc: Detect potential container escape attempts
      condition: >
        spawned_process and container and
        (proc.cmdline contains "nsenter" or
         proc.cmdline contains "docker" or
         proc.cmdline contains "crictl" or
         fd.name = "/proc/1/ns/mnt" or
         fd.name startswith "/host")
      output: >
        Container escape attempt detected
        (user=%user.name command=%proc.cmdline
        container_id=%container.id
        container_name=%container.name
        image=%container.image.repository)
      priority: CRITICAL
      tags: [container, escape, mitre_privilege_escalation]
```

## 📋 Infrastructure Hardening Checklist

### Container Host
- [ ] CIS Level 2 benchmarks applied
- [ ] Auditd configured and running
- [ ] SSH hardened per CIS guidelines
- [ ] Network parameters secured
- [ ] Unnecessary services disabled
- [ ] Kernel parameters hardened
- [ ] File permissions verified

### Docker Daemon
- [ ] TLS enabled for remote access
- [ ] User namespace remapping enabled
- [ ] Seccomp profile applied
- [ ] AppArmor/SELinux enabled
- [ ] Inter-container communication disabled by default
- [ ] Live restore enabled
- [ ] Logging configured

### Container Images
- [ ] Minimal base images used
- [ ] Non-root user configured
- [ ] No secrets in image layers
- [ ] Multi-stage builds implemented
- [ ] Security scanning in CI/CD
- [ ] SBOM generated
- [ ] Images signed

### Kubernetes
- [ ] RBAC properly configured
- [ ] Network policies implemented
- [ ] Pod security standards enforced
- [ ] Secrets encrypted at rest
- [ ] Audit logging enabled
- [ ] API server hardened
- [ ] etcd encrypted

### Runtime Security
- [ ] Falco or equivalent deployed
- [ ] Runtime scanning enabled
- [ ] Admission controllers configured
- [ ] Policy enforcement active
- [ ] Anomaly detection enabled

---

**Agent Version:** 1.0
**Last Updated:** 2025-12-02
**Expertise Level:** Expert
**Frameworks:** CIS Benchmarks, NIST, STIG, PCI-DSS
