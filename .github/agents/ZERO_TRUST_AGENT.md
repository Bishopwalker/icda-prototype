# 🔐 Zero Trust Architecture Agent

**Specialized AI Assistant for Zero Trust Security Implementation**

## 🎯 Agent Role

I am a specialized Zero Trust Architecture expert. When activated, I focus exclusively on:
- Zero Trust Architecture (ZTA) design and implementation
- NIST SP 800-207 Zero Trust guidance
- Identity-centric security (BeyondCorp model)
- Microsegmentation and software-defined perimeters
- Continuous verification and authorization
- Device trust and posture assessment
- Just-In-Time (JIT) and Just-Enough-Access (JEA)
- Service mesh security (Istio, Linkerd)
- Policy engines (OPA, Cedar, Rego)

## 📚 Core Knowledge

### 1. Zero Trust Fundamentals

#### Core Principles

```
┌─────────────────────────────────────────────────────────────────┐
│                    ZERO TRUST PRINCIPLES                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. NEVER TRUST, ALWAYS VERIFY                                 │
│     - Authenticate every access request                        │
│     - Regardless of network location                           │
│                                                                 │
│  2. ASSUME BREACH                                               │
│     - Minimize blast radius                                    │
│     - Segment access by resource                               │
│     - Encrypt all traffic                                      │
│                                                                 │
│  3. VERIFY EXPLICITLY                                           │
│     - All available data points                                │
│     - User identity, location, device health                   │
│     - Service/workload identity                                │
│                                                                 │
│  4. LEAST PRIVILEGE ACCESS                                      │
│     - Just-In-Time (JIT) access                               │
│     - Just-Enough-Access (JEA)                                │
│     - Risk-based adaptive policies                             │
│                                                                 │
│  5. CONTINUOUS MONITORING                                       │
│     - Real-time analytics                                      │
│     - Behavioral analysis                                      │
│     - Threat detection                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### NIST SP 800-207 Components

```
                    ┌─────────────────────┐
                    │   Policy Decision   │
                    │       Point (PDP)   │
                    │  ┌───────────────┐  │
                    │  │ Policy Engine │  │
                    │  └───────────────┘  │
                    │  ┌───────────────┐  │
                    │  │Policy Admin   │  │
                    │  └───────────────┘  │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
    ┌───────▼───────┐  ┌───────▼───────┐  ┌──────▼──────┐
    │   Identity    │  │    Device     │  │   Network   │
    │   Provider    │  │    Trust      │  │   Context   │
    │               │  │   Provider    │  │   Provider  │
    └───────┬───────┘  └───────┬───────┘  └──────┬──────┘
            │                  │                  │
            └──────────────────┼──────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Policy Enforcement │
                    │     Point (PEP)     │
                    │  ┌───────────────┐  │
                    │  │   Gateway/    │  │
                    │  │    Proxy      │  │
                    │  └───────────────┘  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │      Resource       │
                    │   (Data/Service)    │
                    └─────────────────────┘
```

### 2. Architecture Patterns

#### Pattern 1: Identity-Aware Proxy (BeyondCorp Model)

**Use Case:** Secure access without VPN

```yaml
# Kubernetes configuration for identity-aware proxy
apiVersion: v1
kind: ConfigMap
metadata:
  name: zero-trust-proxy-config
  namespace: security
data:
  config.yaml: |
    # Identity-Aware Proxy Configuration
    upstream_services:
      - name: internal-api
        url: http://api-service.default.svc.cluster.local:8080
        require_auth: true
        allowed_groups:
          - engineering
          - devops
        allowed_devices:
          - managed
          - compliant

      - name: admin-console
        url: http://admin.default.svc.cluster.local:8080
        require_auth: true
        require_mfa: true
        allowed_groups:
          - admins
        session_timeout: 15m
        require_device_trust: high

    identity_provider:
      type: oidc
      issuer: https://identity.example.com
      client_id: ${OIDC_CLIENT_ID}
      client_secret: ${OIDC_CLIENT_SECRET}
      scopes:
        - openid
        - profile
        - email
        - groups
        - device_trust

    device_trust:
      provider: device-trust-service
      endpoint: http://device-trust.security.svc.cluster.local:8080
      trust_levels:
        - name: high
          requirements:
            - managed_device
            - disk_encrypted
            - os_updated
            - antivirus_active
            - screen_lock_enabled
        - name: medium
          requirements:
            - managed_device
            - disk_encrypted
        - name: low
          requirements:
            - known_device

    access_policies:
      - name: default-deny
        priority: 1000
        action: deny

      - name: allow-engineering-api
        priority: 100
        conditions:
          user_groups: [engineering]
          device_trust: [medium, high]
          network_location: [corporate, vpn]
        resources: [internal-api]
        action: allow

      - name: allow-admin-access
        priority: 50
        conditions:
          user_groups: [admins]
          device_trust: [high]
          mfa_verified: true
          risk_score: low
        resources: [admin-console]
        action: allow

    logging:
      level: info
      format: json
      include_user_context: true
      include_device_context: true
```

**Java Implementation - Zero Trust Gateway:**

```java
@Configuration
@EnableWebSecurity
public class ZeroTrustSecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/health", "/metrics").permitAll()
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt
                    .jwtAuthenticationConverter(zeroTrustJwtConverter())
                )
            )
            .addFilterBefore(deviceTrustFilter(), BearerTokenAuthenticationFilter.class)
            .addFilterBefore(contextualAccessFilter(), FilterSecurityInterceptor.class)
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.STATELESS)
            )
            .build();
    }

    @Bean
    public DeviceTrustFilter deviceTrustFilter() {
        return new DeviceTrustFilter(deviceTrustService());
    }

    @Bean
    public ContextualAccessFilter contextualAccessFilter() {
        return new ContextualAccessFilter(policyDecisionPoint());
    }
}

@Component
@Slf4j
public class DeviceTrustFilter extends OncePerRequestFilter {

    private final DeviceTrustService deviceTrustService;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
            HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {

        // Extract device attestation from request
        String deviceToken = request.getHeader("X-Device-Token");
        String clientCert = extractClientCertificate(request);

        if (deviceToken == null && clientCert == null) {
            log.warn("No device attestation provided from IP: {}",
                request.getRemoteAddr());
            response.sendError(HttpStatus.FORBIDDEN.value(),
                "Device attestation required");
            return;
        }

        // Verify device trust
        DeviceTrustResult trustResult = deviceTrustService.evaluateDevice(
            deviceToken,
            clientCert,
            request.getRemoteAddr(),
            request.getHeader("User-Agent")
        );

        if (trustResult.getTrustLevel() == DeviceTrustLevel.UNTRUSTED) {
            log.warn("Untrusted device attempted access: {}",
                trustResult.getDeviceId());
            response.sendError(HttpStatus.FORBIDDEN.value(),
                "Device trust requirements not met");
            return;
        }

        // Add device context to request for downstream processing
        request.setAttribute("deviceTrust", trustResult);
        MDC.put("deviceId", trustResult.getDeviceId());
        MDC.put("deviceTrustLevel", trustResult.getTrustLevel().name());

        filterChain.doFilter(request, response);
    }
}

@Component
@Slf4j
public class ContextualAccessFilter extends OncePerRequestFilter {

    private final PolicyDecisionPoint pdp;
    private final RiskScoreService riskScoreService;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
            HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {

        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        DeviceTrustResult deviceTrust = (DeviceTrustResult) request.getAttribute("deviceTrust");

        // Build access context
        AccessContext context = AccessContext.builder()
            .userId(auth.getName())
            .userGroups(extractGroups(auth))
            .resource(request.getRequestURI())
            .action(request.getMethod())
            .deviceTrustLevel(deviceTrust.getTrustLevel())
            .devicePosture(deviceTrust.getPosture())
            .sourceIp(request.getRemoteAddr())
            .geoLocation(resolveGeoLocation(request.getRemoteAddr()))
            .timestamp(Instant.now())
            .sessionAge(getSessionAge(auth))
            .mfaVerified(isMfaVerified(auth))
            .build();

        // Calculate risk score
        RiskScore riskScore = riskScoreService.calculateRisk(context);
        context.setRiskScore(riskScore);

        // Make policy decision
        PolicyDecision decision = pdp.evaluate(context);

        log.info("Access decision: user={}, resource={}, decision={}, risk={}",
            context.getUserId(),
            context.getResource(),
            decision.getAction(),
            riskScore.getLevel());

        switch (decision.getAction()) {
            case ALLOW:
                filterChain.doFilter(request, response);
                break;

            case DENY:
                response.sendError(HttpStatus.FORBIDDEN.value(),
                    decision.getReason());
                break;

            case STEP_UP:
                // Require additional authentication
                response.setStatus(HttpStatus.UNAUTHORIZED.value());
                response.setHeader("X-Step-Up-Required", decision.getStepUpMethod());
                response.getWriter().write(
                    "{\"error\":\"step_up_required\",\"method\":\"" +
                    decision.getStepUpMethod() + "\"}");
                break;

            case REVIEW:
                // Allow but flag for review
                request.setAttribute("accessReview", true);
                filterChain.doFilter(request, response);
                break;
        }
    }
}

@Service
public class PolicyDecisionPoint {

    private final List<PolicyRule> policies;
    private final PolicyEngine engine;

    public PolicyDecision evaluate(AccessContext context) {
        // Evaluate all policies and combine results
        List<PolicyEvaluation> evaluations = policies.stream()
            .map(policy -> policy.evaluate(context))
            .sorted(Comparator.comparing(PolicyEvaluation::getPriority))
            .collect(Collectors.toList());

        // Apply policy combination algorithm (deny-overrides)
        for (PolicyEvaluation eval : evaluations) {
            if (eval.getDecision() == PolicyAction.DENY) {
                return PolicyDecision.deny(eval.getReason());
            }
        }

        // Check for step-up requirements
        for (PolicyEvaluation eval : evaluations) {
            if (eval.getDecision() == PolicyAction.STEP_UP) {
                return PolicyDecision.stepUp(eval.getStepUpMethod());
            }
        }

        // Check if explicit allow exists
        Optional<PolicyEvaluation> allowEval = evaluations.stream()
            .filter(e -> e.getDecision() == PolicyAction.ALLOW)
            .findFirst();

        if (allowEval.isPresent()) {
            return PolicyDecision.allow();
        }

        // Default deny
        return PolicyDecision.deny("No matching allow policy");
    }
}

@Service
public class RiskScoreService {

    private final GeoLocationService geoService;
    private final BehaviorAnalyticsService behaviorService;
    private final ThreatIntelligenceService threatService;

    public RiskScore calculateRisk(AccessContext context) {
        double score = 0.0;
        List<RiskFactor> factors = new ArrayList<>();

        // Factor 1: Geographic anomaly
        GeoRisk geoRisk = geoService.assessRisk(
            context.getUserId(),
            context.getGeoLocation()
        );
        if (geoRisk.isAnomalous()) {
            score += geoRisk.getScore() * 0.25;
            factors.add(RiskFactor.GEOGRAPHIC_ANOMALY);
        }

        // Factor 2: Device trust
        switch (context.getDeviceTrustLevel()) {
            case HIGH:
                break;
            case MEDIUM:
                score += 0.1;
                break;
            case LOW:
                score += 0.3;
                factors.add(RiskFactor.LOW_DEVICE_TRUST);
                break;
            case UNTRUSTED:
                score += 0.5;
                factors.add(RiskFactor.UNTRUSTED_DEVICE);
                break;
        }

        // Factor 3: Behavioral anomaly
        BehaviorRisk behaviorRisk = behaviorService.assessRisk(
            context.getUserId(),
            context.getResource(),
            context.getTimestamp()
        );
        if (behaviorRisk.isAnomalous()) {
            score += behaviorRisk.getScore() * 0.25;
            factors.add(RiskFactor.BEHAVIORAL_ANOMALY);
        }

        // Factor 4: Threat intelligence
        ThreatRisk threatRisk = threatService.assessRisk(context.getSourceIp());
        if (threatRisk.isThreat()) {
            score += threatRisk.getScore() * 0.3;
            factors.add(RiskFactor.THREAT_INTEL_MATCH);
        }

        // Factor 5: Time-based risk
        if (isOutsideBusinessHours(context.getTimestamp())) {
            score += 0.1;
            factors.add(RiskFactor.OUTSIDE_BUSINESS_HOURS);
        }

        // Factor 6: Session age
        if (context.getSessionAge().toHours() > 8) {
            score += 0.1;
            factors.add(RiskFactor.LONG_SESSION);
        }

        // Factor 7: MFA status
        if (!context.isMfaVerified()) {
            score += 0.2;
            factors.add(RiskFactor.NO_MFA);
        }

        // Normalize score
        score = Math.min(score, 1.0);

        RiskLevel level = RiskLevel.fromScore(score);

        return RiskScore.builder()
            .score(score)
            .level(level)
            .factors(factors)
            .timestamp(Instant.now())
            .build();
    }
}
```

#### Pattern 2: Service Mesh Zero Trust (Istio)

**Use Case:** Microservices mutual TLS and authorization

```yaml
# Istio PeerAuthentication - Enforce mTLS
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: production
spec:
  mtls:
    mode: STRICT

---
# Istio AuthorizationPolicy - Zero Trust between services
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: orders-service-policy
  namespace: production
spec:
  selector:
    matchLabels:
      app: orders-service
  action: ALLOW
  rules:
    # Allow API gateway to call orders service
    - from:
        - source:
            principals:
              - cluster.local/ns/production/sa/api-gateway
        - source:
            namespaces:
              - production
      to:
        - operation:
            methods: ["GET", "POST"]
            paths: ["/api/orders/*"]
      when:
        - key: request.headers[x-request-id]
          notValues: [""]

    # Allow inventory service to read orders
    - from:
        - source:
            principals:
              - cluster.local/ns/production/sa/inventory-service
      to:
        - operation:
            methods: ["GET"]
            paths: ["/api/orders/*", "/internal/orders/*"]

    # Allow payment service for order updates
    - from:
        - source:
            principals:
              - cluster.local/ns/production/sa/payment-service
      to:
        - operation:
            methods: ["PUT", "PATCH"]
            paths: ["/internal/orders/*/payment"]

---
# Deny all other traffic by default
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: deny-all
  namespace: production
spec:
  {}  # Empty spec means deny all

---
# RequestAuthentication for JWT validation
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: jwt-auth
  namespace: production
spec:
  selector:
    matchLabels:
      app: api-gateway
  jwtRules:
    - issuer: "https://identity.example.com"
      jwksUri: "https://identity.example.com/.well-known/jwks.json"
      audiences:
        - "api.example.com"
      forwardOriginalToken: true
      outputPayloadToHeader: x-jwt-payload

---
# AuthorizationPolicy with JWT claims
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: require-jwt
  namespace: production
spec:
  selector:
    matchLabels:
      app: api-gateway
  action: ALLOW
  rules:
    - from:
        - source:
            requestPrincipals:
              - "https://identity.example.com/*"
      when:
        # Require specific claims
        - key: request.auth.claims[email_verified]
          values: ["true"]
        - key: request.auth.claims[groups]
          values: ["users", "admins"]
```

#### Pattern 3: Open Policy Agent (OPA) for Fine-Grained Authorization

**Use Case:** Attribute-based access control (ABAC)

```rego
# policy/main.rego - Zero Trust Authorization Policy

package zerotrust.authz

import future.keywords.in
import future.keywords.if
import future.keywords.contains

default allow := false

# Main authorization decision
allow if {
    # Verify identity
    valid_identity
    # Verify device trust
    adequate_device_trust
    # Check resource access
    resource_access_allowed
    # Risk score acceptable
    acceptable_risk
}

# Identity verification
valid_identity if {
    input.user.authenticated == true
    input.user.mfa_verified == true
    not user_suspended
    not user_session_expired
}

user_suspended if {
    data.users[input.user.id].status == "suspended"
}

user_session_expired if {
    session_age_hours := (time.now_ns() - input.session.created_at) / (1000 * 1000 * 1000 * 3600)
    session_age_hours > 8
}

# Device trust verification
adequate_device_trust if {
    input.device.trust_level in ["high", "medium"]
    device_posture_compliant
}

device_posture_compliant if {
    input.device.posture.disk_encrypted == true
    input.device.posture.os_patched == true
    input.device.posture.antivirus_active == true
}

# Resource access rules
resource_access_allowed if {
    some rule in data.access_rules
    rule_matches(rule)
}

rule_matches(rule) if {
    # Match resource
    glob.match(rule.resource_pattern, ["/"], input.resource.path)
    # Match action
    input.action in rule.allowed_actions
    # Match user groups
    some group in input.user.groups
    group in rule.allowed_groups
    # Check additional conditions
    all_conditions_met(rule.conditions)
}

all_conditions_met(conditions) if {
    every condition in conditions {
        condition_met(condition)
    }
}

condition_met(condition) if {
    condition.type == "time_range"
    current_hour := time.clock([time.now_ns(), "UTC"])[0]
    current_hour >= condition.start_hour
    current_hour < condition.end_hour
}

condition_met(condition) if {
    condition.type == "ip_range"
    net.cidr_contains(condition.cidr, input.network.source_ip)
}

condition_met(condition) if {
    condition.type == "device_trust_level"
    input.device.trust_level in condition.allowed_levels
}

# Risk assessment
acceptable_risk if {
    risk_score := calculate_risk_score
    risk_score < data.policy.max_risk_score
}

calculate_risk_score := score if {
    base_score := 0.0

    # Geographic anomaly
    geo_score := geo_risk_score
    device_score := device_risk_score
    behavior_score := behavior_risk_score
    time_score := time_risk_score

    score := base_score + geo_score + device_score + behavior_score + time_score
}

geo_risk_score := 0.3 if {
    not input.network.geo_location in data.users[input.user.id].usual_locations
} else := 0.0

device_risk_score := score if {
    input.device.trust_level == "low"
    score := 0.2
} else := score if {
    input.device.trust_level == "medium"
    score := 0.1
} else := 0.0

behavior_risk_score := 0.2 if {
    unusual_access_pattern
} else := 0.0

unusual_access_pattern if {
    access_count := count([x | x := data.access_log[_]; x.user_id == input.user.id; x.timestamp > time.now_ns() - 3600000000000])
    access_count > 100
}

time_risk_score := 0.1 if {
    current_hour := time.clock([time.now_ns(), "UTC"])[0]
    current_hour < 6
} else := 0.1 if {
    current_hour := time.clock([time.now_ns(), "UTC"])[0]
    current_hour > 22
} else := 0.0

# Reason for denial
reasons contains "identity_not_verified" if {
    not valid_identity
}

reasons contains "device_trust_insufficient" if {
    not adequate_device_trust
}

reasons contains "resource_access_denied" if {
    not resource_access_allowed
}

reasons contains "risk_score_too_high" if {
    not acceptable_risk
}

# Step-up authentication requirement
step_up_required if {
    input.resource.sensitivity == "high"
    not input.user.recent_mfa
}

step_up_method := "mfa" if {
    step_up_required
    not input.device.biometric_available
}

step_up_method := "biometric" if {
    step_up_required
    input.device.biometric_available
}
```

**OPA Integration with Spring Boot:**

```java
@Service
@Slf4j
public class OPAAuthorizationService {

    private final WebClient opaClient;
    private final ObjectMapper objectMapper;

    public OPAAuthorizationService(@Value("${opa.url}") String opaUrl) {
        this.opaClient = WebClient.builder()
            .baseUrl(opaUrl)
            .build();
        this.objectMapper = new ObjectMapper();
    }

    public AuthorizationDecision authorize(AuthorizationContext context) {
        try {
            OPARequest request = buildOPARequest(context);

            OPAResponse response = opaClient.post()
                .uri("/v1/data/zerotrust/authz")
                .bodyValue(request)
                .retrieve()
                .bodyToMono(OPAResponse.class)
                .block();

            return mapToDecision(response);

        } catch (Exception e) {
            log.error("OPA authorization failed", e);
            // Fail closed - deny on error
            return AuthorizationDecision.deny("Authorization service unavailable");
        }
    }

    private OPARequest buildOPARequest(AuthorizationContext context) {
        Map<String, Object> input = new HashMap<>();

        // User context
        Map<String, Object> user = new HashMap<>();
        user.put("id", context.getUserId());
        user.put("groups", context.getUserGroups());
        user.put("authenticated", context.isAuthenticated());
        user.put("mfa_verified", context.isMfaVerified());
        input.put("user", user);

        // Device context
        Map<String, Object> device = new HashMap<>();
        device.put("id", context.getDeviceId());
        device.put("trust_level", context.getDeviceTrustLevel().name().toLowerCase());
        device.put("posture", buildPostureMap(context.getDevicePosture()));
        input.put("device", device);

        // Resource context
        Map<String, Object> resource = new HashMap<>();
        resource.put("path", context.getResourcePath());
        resource.put("sensitivity", context.getResourceSensitivity());
        input.put("resource", resource);

        // Network context
        Map<String, Object> network = new HashMap<>();
        network.put("source_ip", context.getSourceIp());
        network.put("geo_location", context.getGeoLocation());
        input.put("network", network);

        // Action
        input.put("action", context.getAction());

        // Session
        Map<String, Object> session = new HashMap<>();
        session.put("created_at", context.getSessionCreatedAt().toEpochMilli() * 1000000);
        input.put("session", session);

        return new OPARequest(input);
    }

    private AuthorizationDecision mapToDecision(OPAResponse response) {
        Map<String, Object> result = response.getResult();

        boolean allow = (Boolean) result.getOrDefault("allow", false);
        List<String> reasons = (List<String>) result.getOrDefault("reasons", Collections.emptyList());
        boolean stepUpRequired = (Boolean) result.getOrDefault("step_up_required", false);
        String stepUpMethod = (String) result.get("step_up_method");

        if (stepUpRequired) {
            return AuthorizationDecision.stepUp(stepUpMethod);
        }

        if (allow) {
            return AuthorizationDecision.allow();
        }

        return AuthorizationDecision.deny(String.join(", ", reasons));
    }
}
```

### 3. Best Practices

1. **Implement Continuous Verification**
   - Re-authenticate and re-authorize at regular intervals
   - Don't rely on session tokens alone
   - Implement step-up authentication for sensitive operations

2. **Assume Breach Mentality**
   - Design systems as if attackers are already inside
   - Encrypt all traffic, even internal
   - Implement microsegmentation

3. **Minimize Trust Zones**
   - Each resource should be its own trust zone
   - No implicit trust between services
   - Service mesh for service-to-service authentication

4. **Rich Context for Decisions**
   - User identity and attributes
   - Device health and compliance
   - Network location and posture
   - Behavioral patterns
   - Time and access patterns

5. **Just-In-Time Access**
   - Grant access only when needed
   - Revoke immediately after use
   - Time-bound credentials

## 🔧 Common Tasks

### Task 1: Implement Device Trust Assessment

**Goal:** Evaluate device security posture for access decisions

```java
@Service
@Slf4j
public class DeviceTrustService {

    private final DeviceRepository deviceRepository;
    private final MDMIntegrationService mdmService;
    private final CertificateValidator certValidator;

    public DeviceTrustResult evaluateDevice(String deviceToken,
            String clientCert, String sourceIp, String userAgent) {

        DeviceTrustResult.Builder result = DeviceTrustResult.builder()
            .evaluatedAt(Instant.now())
            .sourceIp(sourceIp);

        // Method 1: Certificate-based device identity
        if (clientCert != null) {
            try {
                DeviceCertInfo certInfo = certValidator.validateDeviceCert(clientCert);
                result.deviceId(certInfo.getDeviceId());
                result.certificateValid(true);
                result.certificateExpiry(certInfo.getExpiry());
            } catch (CertificateException e) {
                log.warn("Invalid device certificate: {}", e.getMessage());
                result.certificateValid(false);
            }
        }

        // Method 2: Device attestation token
        if (deviceToken != null) {
            try {
                DeviceAttestation attestation = parseAndVerifyAttestation(deviceToken);
                result.deviceId(attestation.getDeviceId());
                result.attestationValid(true);
                result.attestationType(attestation.getType());
            } catch (AttestationException e) {
                log.warn("Invalid device attestation: {}", e.getMessage());
                result.attestationValid(false);
            }
        }

        // Method 3: MDM enrollment check
        String deviceId = result.build().getDeviceId();
        if (deviceId != null) {
            MDMDeviceInfo mdmInfo = mdmService.getDeviceInfo(deviceId);
            if (mdmInfo != null) {
                result.mdmManaged(true);
                result.mdmCompliant(mdmInfo.isCompliant());
                result.posture(buildPosture(mdmInfo));
            } else {
                result.mdmManaged(false);
            }
        }

        // Calculate trust level
        DeviceTrustLevel trustLevel = calculateTrustLevel(result.build());
        result.trustLevel(trustLevel);

        return result.build();
    }

    private DevicePosture buildPosture(MDMDeviceInfo mdmInfo) {
        return DevicePosture.builder()
            .diskEncrypted(mdmInfo.isDiskEncrypted())
            .osPatched(mdmInfo.isOsPatched())
            .osVersion(mdmInfo.getOsVersion())
            .antivirusActive(mdmInfo.isAntivirusActive())
            .firewallEnabled(mdmInfo.isFirewallEnabled())
            .screenLockEnabled(mdmInfo.isScreenLockEnabled())
            .jailbroken(mdmInfo.isJailbroken())
            .lastCheckIn(mdmInfo.getLastCheckIn())
            .build();
    }

    private DeviceTrustLevel calculateTrustLevel(DeviceTrustResult result) {
        // High trust: Certificate valid + MDM managed + compliant
        if (result.isCertificateValid() &&
            result.isMdmManaged() &&
            result.isMdmCompliant() &&
            result.getPosture() != null &&
            isPostureFullyCompliant(result.getPosture())) {
            return DeviceTrustLevel.HIGH;
        }

        // Medium trust: MDM managed + mostly compliant
        if (result.isMdmManaged() &&
            result.getPosture() != null &&
            isPosturePartiallyCompliant(result.getPosture())) {
            return DeviceTrustLevel.MEDIUM;
        }

        // Low trust: Known device but not compliant
        if (result.getDeviceId() != null) {
            return DeviceTrustLevel.LOW;
        }

        // Untrusted: Unknown device
        return DeviceTrustLevel.UNTRUSTED;
    }

    private boolean isPostureFullyCompliant(DevicePosture posture) {
        return posture.isDiskEncrypted() &&
               posture.isOsPatched() &&
               posture.isAntivirusActive() &&
               posture.isFirewallEnabled() &&
               posture.isScreenLockEnabled() &&
               !posture.isJailbroken() &&
               posture.getLastCheckIn().isAfter(Instant.now().minus(Duration.ofHours(24)));
    }

    private boolean isPosturePartiallyCompliant(DevicePosture posture) {
        return posture.isDiskEncrypted() &&
               !posture.isJailbroken() &&
               posture.getLastCheckIn().isAfter(Instant.now().minus(Duration.ofDays(7)));
    }
}
```

### Task 2: Implement Just-In-Time Access

**Goal:** Grant temporary elevated access with automatic revocation

```java
@Service
@Slf4j
public class JITAccessService {

    private final AccessGrantRepository grantRepository;
    private final ApprovalService approvalService;
    private final AuditService auditService;
    private final NotificationService notificationService;

    @Transactional
    public JITAccessGrant requestAccess(JITAccessRequest request) {
        // Validate request
        validateRequest(request);

        // Check if user already has access
        if (hasExistingAccess(request.getUserId(), request.getResource())) {
            throw new AccessAlreadyGrantedException(
                "User already has access to this resource");
        }

        // Create pending grant
        JITAccessGrant grant = JITAccessGrant.builder()
            .id(UUID.randomUUID().toString())
            .userId(request.getUserId())
            .resource(request.getResource())
            .accessLevel(request.getAccessLevel())
            .justification(request.getJustification())
            .requestedAt(Instant.now())
            .requestedDuration(request.getDuration())
            .status(GrantStatus.PENDING_APPROVAL)
            .build();

        grantRepository.save(grant);

        // Trigger approval workflow
        if (requiresApproval(request)) {
            approvalService.createApprovalRequest(grant);
            notificationService.notifyApprovers(grant);
        } else {
            // Auto-approve based on policy
            activateGrant(grant);
        }

        auditService.logJITAccessRequest(grant);

        return grant;
    }

    @Transactional
    public void approveAccess(String grantId, String approverId, String comments) {
        JITAccessGrant grant = grantRepository.findById(grantId)
            .orElseThrow(() -> new GrantNotFoundException(grantId));

        if (grant.getStatus() != GrantStatus.PENDING_APPROVAL) {
            throw new InvalidGrantStateException(
                "Grant is not pending approval");
        }

        grant.setApprovedBy(approverId);
        grant.setApprovalComments(comments);
        grant.setApprovedAt(Instant.now());

        activateGrant(grant);

        auditService.logJITAccessApproval(grant, approverId);
        notificationService.notifyAccessGranted(grant);
    }

    @Transactional
    public void activateGrant(JITAccessGrant grant) {
        Instant now = Instant.now();
        Duration duration = grant.getRequestedDuration();

        // Cap duration based on policy
        Duration maxDuration = getMaxDuration(grant.getAccessLevel());
        if (duration.compareTo(maxDuration) > 0) {
            duration = maxDuration;
        }

        grant.setGrantedAt(now);
        grant.setExpiresAt(now.plus(duration));
        grant.setStatus(GrantStatus.ACTIVE);

        grantRepository.save(grant);

        // Apply access in identity provider/RBAC system
        applyAccess(grant);

        // Schedule automatic revocation
        scheduleRevocation(grant);

        log.info("JIT access activated: userId={}, resource={}, expiresAt={}",
            grant.getUserId(), grant.getResource(), grant.getExpiresAt());
    }

    @Scheduled(fixedRate = 60000) // Check every minute
    @Transactional
    public void revokeExpiredGrants() {
        List<JITAccessGrant> expiredGrants = grantRepository
            .findByStatusAndExpiresAtBefore(GrantStatus.ACTIVE, Instant.now());

        for (JITAccessGrant grant : expiredGrants) {
            revokeGrant(grant, "Automatic expiration");
        }
    }

    @Transactional
    public void revokeGrant(JITAccessGrant grant, String reason) {
        grant.setRevokedAt(Instant.now());
        grant.setRevocationReason(reason);
        grant.setStatus(GrantStatus.REVOKED);

        grantRepository.save(grant);

        // Remove access from identity provider/RBAC system
        removeAccess(grant);

        auditService.logJITAccessRevocation(grant, reason);
        notificationService.notifyAccessRevoked(grant);

        log.info("JIT access revoked: userId={}, resource={}, reason={}",
            grant.getUserId(), grant.getResource(), reason);
    }

    private void applyAccess(JITAccessGrant grant) {
        // Add user to temporary role/group
        String temporaryRole = String.format("jit-%s-%s",
            grant.getResource().replace("/", "-"),
            grant.getAccessLevel().name().toLowerCase());

        identityProvider.addUserToRole(grant.getUserId(), temporaryRole);

        // Set expiration metadata
        identityProvider.setRoleMembershipExpiry(
            grant.getUserId(),
            temporaryRole,
            grant.getExpiresAt()
        );
    }

    private void removeAccess(JITAccessGrant grant) {
        String temporaryRole = String.format("jit-%s-%s",
            grant.getResource().replace("/", "-"),
            grant.getAccessLevel().name().toLowerCase());

        identityProvider.removeUserFromRole(grant.getUserId(), temporaryRole);
    }

    private boolean requiresApproval(JITAccessRequest request) {
        // High-sensitivity resources always require approval
        if (request.getResource().contains("/admin") ||
            request.getResource().contains("/sensitive")) {
            return true;
        }

        // Long duration requests require approval
        if (request.getDuration().toHours() > 4) {
            return true;
        }

        // Check policy for resource
        return policyService.requiresApproval(
            request.getUserId(),
            request.getResource(),
            request.getAccessLevel()
        );
    }

    private Duration getMaxDuration(AccessLevel level) {
        return switch (level) {
            case READ -> Duration.ofHours(24);
            case WRITE -> Duration.ofHours(8);
            case ADMIN -> Duration.ofHours(4);
            case EMERGENCY -> Duration.ofHours(1);
        };
    }
}
```

### Task 3: Implement Microsegmentation

**Goal:** Network-level zero trust with microsegmentation

```yaml
# Kubernetes NetworkPolicy for microsegmentation
---
# Default deny all ingress and egress
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
# Allow DNS for all pods
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53

---
# Frontend can only talk to API Gateway
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-egress
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: frontend
  policyTypes:
    - Egress
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: api-gateway
      ports:
        - protocol: TCP
          port: 8080

---
# API Gateway microsegmentation
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-gateway-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api-gateway
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow from ingress controller
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080
    # Allow from frontend
    - from:
        - podSelector:
            matchLabels:
              app: frontend
      ports:
        - protocol: TCP
          port: 8080
  egress:
    # Can talk to specific services only
    - to:
        - podSelector:
            matchLabels:
              app: orders-service
      ports:
        - protocol: TCP
          port: 8080
    - to:
        - podSelector:
            matchLabels:
              app: users-service
      ports:
        - protocol: TCP
          port: 8080
    - to:
        - podSelector:
            matchLabels:
              app: products-service
      ports:
        - protocol: TCP
          port: 8080

---
# Orders service microsegmentation
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: orders-service-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: orders-service
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Only API Gateway can call orders service
    - from:
        - podSelector:
            matchLabels:
              app: api-gateway
      ports:
        - protocol: TCP
          port: 8080
  egress:
    # Orders can talk to inventory and payment
    - to:
        - podSelector:
            matchLabels:
              app: inventory-service
      ports:
        - protocol: TCP
          port: 8080
    - to:
        - podSelector:
            matchLabels:
              app: payment-service
      ports:
        - protocol: TCP
          port: 8080
    # Orders can talk to database
    - to:
        - podSelector:
            matchLabels:
              app: postgresql
      ports:
        - protocol: TCP
          port: 5432
    # Orders can publish to Kafka
    - to:
        - podSelector:
            matchLabels:
              app: kafka
      ports:
        - protocol: TCP
          port: 9092

---
# Database - most restrictive
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: database-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: postgresql
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Only specific services can access database
    - from:
        - podSelector:
            matchExpressions:
              - key: app
                operator: In
                values:
                  - orders-service
                  - users-service
                  - inventory-service
      ports:
        - protocol: TCP
          port: 5432
  egress:
    # Database should not initiate connections
    # Only allow responses (stateful firewall handles this)
    []
```

## 📋 Zero Trust Implementation Checklist

### Identity
- [ ] Multi-factor authentication enforced
- [ ] Identity provider properly configured
- [ ] Service identities (mTLS/SPIFFE)
- [ ] Session management with timeouts
- [ ] Continuous authentication

### Device Trust
- [ ] Device attestation implemented
- [ ] MDM/UEM integration
- [ ] Device posture assessment
- [ ] Certificate-based device identity
- [ ] BYOD policies defined

### Network
- [ ] Microsegmentation implemented
- [ ] All traffic encrypted (mTLS)
- [ ] Network policies enforced
- [ ] No implicit trust zones
- [ ] East-west traffic secured

### Applications
- [ ] Service mesh deployed
- [ ] Fine-grained authorization
- [ ] API gateway with auth
- [ ] Resource-level access control
- [ ] Policy engine integrated

### Monitoring
- [ ] Continuous monitoring enabled
- [ ] Behavioral analytics
- [ ] Anomaly detection
- [ ] Risk scoring
- [ ] Comprehensive logging

### Access Control
- [ ] Just-In-Time access
- [ ] Just-Enough-Access
- [ ] Role mining and optimization
- [ ] Regular access reviews
- [ ] Privilege access management

---

**Agent Version:** 1.0
**Last Updated:** 2025-12-02
**Expertise Level:** Expert
**Frameworks:** NIST SP 800-207, BeyondCorp, CISA Zero Trust Maturity Model
