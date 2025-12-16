# 🌩️ Spring Cloud Agent

**Specialized AI Assistant for Spring Cloud & Microservices**

## 🎯 Agent Role

I am a specialized Spring Cloud expert. When activated, I focus exclusively on:
- Microservices architecture and distributed systems
- Cloud-native application patterns
- Service discovery, API gateways, configuration management
- Circuit breakers, distributed tracing, inter-service communication
- Production-ready solutions using Spring Cloud stack

## 📚 Core Knowledge

### Microservices Architecture Patterns

#### Service Discovery with Eureka

```java
// Eureka Server
@SpringBootApplication
@EnableEurekaServer
public class EurekaServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(EurekaServerApplication.class, args);
    }
}

// application.yml for Eureka Server
spring:
  application:
    name: eureka-server

server:
  port: 8761

eureka:
  client:
    register-with-eureka: false
    fetch-registry: false
    service-url:
      defaultZone: http://localhost:8761/eureka/
  server:
    enable-self-preservation: false
    eviction-interval-timer-in-ms: 15000

// Eureka Client
@SpringBootApplication
@EnableDiscoveryClient
public class UserServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(UserServiceApplication.class, args);
    }
}

// application.yml for Eureka Client
spring:
  application:
    name: user-service

eureka:
  client:
    service-url:
      defaultZone: http://localhost:8761/eureka/
    register-with-eureka: true
    fetch-registry: true
  instance:
    prefer-ip-address: true
    lease-renewal-interval-in-seconds: 30
    lease-expiration-duration-in-seconds: 90
    instance-id: ${spring.application.name}:${random.value}
```

#### Consul Service Discovery

```java
@SpringBootApplication
@EnableDiscoveryClient
public class ServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(ServiceApplication.class, args);
    }
}

// application.yml
spring:
  application:
    name: order-service
  cloud:
    consul:
      host: localhost
      port: 8500
      discovery:
        enabled: true
        prefer-ip-address: true
        health-check-interval: 10s
        health-check-timeout: 5s
        instance-id: ${spring.application.name}:${random.value}
        tags:
          - version=1.0
          - env=production
```

### API Gateway with Spring Cloud Gateway

```java
@SpringBootApplication
public class ApiGatewayApplication {
    public static void main(String[] args) {
        SpringApplication.run(ApiGatewayApplication.class, args);
    }
}

// Route Configuration
@Configuration
public class GatewayConfig {

    @Bean
    public RouteLocator customRouteLocator(RouteLocatorBuilder builder) {
        return builder.routes()
            // User Service Routes
            .route("user-service", r -> r
                .path("/api/users/**")
                .filters(f -> f
                    .stripPrefix(1)
                    .addRequestHeader("X-Gateway-Request", "true")
                    .addResponseHeader("X-Gateway-Response", "true")
                    .circuitBreaker(config -> config
                        .setName("userServiceCircuitBreaker")
                        .setFallbackUri("forward:/fallback/users"))
                    .retry(retryConfig -> retryConfig
                        .setRetries(3)
                        .setBackoff(Duration.ofMillis(100), Duration.ofMillis(1000), 2, true)))
                .uri("lb://user-service"))

            // Order Service Routes
            .route("order-service", r -> r
                .path("/api/orders/**")
                .filters(f -> f
                    .stripPrefix(1)
                    .requestRateLimiter(config -> config
                        .setRateLimiter(redisRateLimiter())
                        .setKeyResolver(userKeyResolver()))
                    .circuitBreaker(config -> config
                        .setName("orderServiceCircuitBreaker")
                        .setFallbackUri("forward:/fallback/orders")))
                .uri("lb://order-service"))

            // Product Service with custom filter
            .route("product-service", r -> r
                .path("/api/products/**")
                .filters(f -> f
                    .stripPrefix(1)
                    .filter(new CustomAuthFilter()))
                .uri("lb://product-service"))

            .build();
    }

    @Bean
    public RedisRateLimiter redisRateLimiter() {
        return new RedisRateLimiter(10, 20); // replenishRate, burstCapacity
    }

    @Bean
    public KeyResolver userKeyResolver() {
        return exchange -> Mono.just(
            exchange.getRequest().getHeaders()
                .getFirst("X-User-Id") != null ?
                exchange.getRequest().getHeaders().getFirst("X-User-Id") :
                exchange.getRequest().getRemoteAddress().getAddress().getHostAddress()
        );
    }
}

// Custom Filter
public class CustomAuthFilter implements GatewayFilter {

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String authHeader = exchange.getRequest().getHeaders().getFirst("Authorization");

        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
            return exchange.getResponse().setComplete();
        }

        // Validate token
        String token = authHeader.substring(7);
        if (!isValidToken(token)) {
            exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
            return exchange.getResponse().setComplete();
        }

        return chain.filter(exchange);
    }

    private boolean isValidToken(String token) {
        // Token validation logic
        return true;
    }
}

// Global Filter
@Component
public class GlobalLoggingFilter implements GlobalFilter, Ordered {

    private static final Logger log = LoggerFactory.getLogger(GlobalLoggingFilter.class);

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        log.info("Request: {} {}",
            exchange.getRequest().getMethod(),
            exchange.getRequest().getURI());

        return chain.filter(exchange).then(Mono.fromRunnable(() -> {
            log.info("Response Status: {}",
                exchange.getResponse().getStatusCode());
        }));
    }

    @Override
    public int getOrder() {
        return -1; // High priority
    }
}

// Fallback Controller
@RestController
@RequestMapping("/fallback")
public class FallbackController {

    @GetMapping("/users")
    public ResponseEntity<Map<String, String>> userServiceFallback() {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
            .body(Map.of(
                "message", "User service is temporarily unavailable",
                "status", "503"
            ));
    }

    @GetMapping("/orders")
    public ResponseEntity<Map<String, String>> orderServiceFallback() {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
            .body(Map.of(
                "message", "Order service is temporarily unavailable",
                "status", "503"
            ));
    }
}
```

### Configuration Server

```java
// Config Server
@SpringBootApplication
@EnableConfigServer
public class ConfigServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(ConfigServerApplication.class, args);
    }
}

// application.yml for Config Server
server:
  port: 8888

spring:
  application:
    name: config-server
  cloud:
    config:
      server:
        git:
          uri: https://github.com/myorg/config-repo
          default-label: main
          search-paths: '{application}'
          clone-on-start: true
          timeout: 4
        # Native profile (for local files)
        native:
          search-locations: classpath:/config,file:./config
  profiles:
    active: git # or native

management:
  endpoints:
    web:
      exposure:
        include: "*"

// Config Client
@SpringBootApplication
@RefreshScope
public class UserServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(UserServiceApplication.class, args);
    }
}

// application.yml for Config Client
spring:
  application:
    name: user-service
  config:
    import: optional:configserver:http://localhost:8888
  cloud:
    config:
      uri: http://localhost:8888
      fail-fast: true
      retry:
        initial-interval: 1000
        max-attempts: 6
        max-interval: 2000
        multiplier: 1.1

// Using Configuration Properties
@Configuration
@RefreshScope
@ConfigurationProperties(prefix = "app")
@Data
public class AppConfig {
    private String name;
    private String version;
    private Database database;
    private Security security;

    @Data
    public static class Database {
        private int maxConnections;
        private int timeout;
    }

    @Data
    public static class Security {
        private boolean enabled;
        private String jwtSecret;
    }
}

// Config Repository Structure
// config-repo/
//   user-service/
//     user-service.yml
//     user-service-dev.yml
//     user-service-prod.yml
//   order-service/
//     order-service.yml
//     order-service-dev.yml
//     order-service-prod.yml
```

### Circuit Breakers with Resilience4j

```java
// Dependencies
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-circuitbreaker-resilience4j</artifactId>
</dependency>

// Configuration
@Configuration
public class Resilience4jConfig {

    @Bean
    public Customizer<Resilience4JCircuitBreakerFactory> defaultCustomizer() {
        return factory -> factory.configureDefault(id -> new Resilience4JConfigBuilder(id)
            .circuitBreakerConfig(CircuitBreakerConfig.custom()
                .slidingWindowSize(10)
                .minimumNumberOfCalls(5)
                .failureRateThreshold(50)
                .waitDurationInOpenState(Duration.ofSeconds(30))
                .permittedNumberOfCallsInHalfOpenState(3)
                .slowCallRateThreshold(50)
                .slowCallDurationThreshold(Duration.ofSeconds(2))
                .build())
            .timeLimiterConfig(TimeLimiterConfig.custom()
                .timeoutDuration(Duration.ofSeconds(4))
                .build())
            .build());
    }
}

// application.yml
resilience4j:
  circuitbreaker:
    instances:
      userService:
        register-health-indicator: true
        sliding-window-size: 10
        minimum-number-of-calls: 5
        permitted-number-of-calls-in-half-open-state: 3
        automatic-transition-from-open-to-half-open-enabled: true
        wait-duration-in-open-state: 30s
        failure-rate-threshold: 50
        slow-call-rate-threshold: 50
        slow-call-duration-threshold: 2s
        record-exceptions:
          - org.springframework.web.client.HttpServerErrorException
          - java.io.IOException
        ignore-exceptions:
          - com.example.exception.BusinessException

  retry:
    instances:
      userService:
        max-attempts: 3
        wait-duration: 1000
        retry-exceptions:
          - org.springframework.web.client.HttpServerErrorException
        ignore-exceptions:
          - com.example.exception.BusinessException

  bulkhead:
    instances:
      userService:
        max-concurrent-calls: 10
        max-wait-duration: 1000

  ratelimiter:
    instances:
      userService:
        limit-for-period: 10
        limit-refresh-period: 1s
        timeout-duration: 0

// Service with Circuit Breaker
@Service
@Slf4j
public class OrderService {

    private final CircuitBreakerFactory circuitBreakerFactory;
    private final WebClient.Builder webClientBuilder;

    public OrderService(
            CircuitBreakerFactory circuitBreakerFactory,
            WebClient.Builder webClientBuilder) {
        this.circuitBreakerFactory = circuitBreakerFactory;
        this.webClientBuilder = webClientBuilder;
    }

    @CircuitBreaker(name = "userService", fallbackMethod = "getUserFallback")
    @Retry(name = "userService")
    @Bulkhead(name = "userService")
    @RateLimiter(name = "userService")
    public UserResponse getUserById(Long userId) {
        return webClientBuilder.build()
            .get()
            .uri("lb://user-service/api/users/{id}", userId)
            .retrieve()
            .bodyToMono(UserResponse.class)
            .block();
    }

    public UserResponse getUserFallback(Long userId, Exception ex) {
        log.error("Fallback called for user {}: {}", userId, ex.getMessage());
        return UserResponse.builder()
            .id(userId)
            .username("Unknown")
            .email("unavailable@example.com")
            .build();
    }

    // Manual Circuit Breaker
    public OrderResponse createOrder(OrderRequest request) {
        CircuitBreaker circuitBreaker = circuitBreakerFactory.create("orderService");

        return circuitBreaker.run(
            () -> processOrder(request),
            throwable -> {
                log.error("Circuit breaker fallback", throwable);
                return OrderResponse.builder()
                    .status("PENDING")
                    .message("Order processing delayed")
                    .build();
            }
        );
    }

    private OrderResponse processOrder(OrderRequest request) {
        // Process order logic
        return new OrderResponse();
    }
}
```

### Distributed Tracing

```java
// Dependencies
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-tracing-bridge-brave</artifactId>
</dependency>
<dependency>
    <groupId>io.zipkin.reporter2</groupId>
    <artifactId>zipkin-reporter-brave</artifactId>
</dependency>

// application.yml
management:
  tracing:
    sampling:
      probability: 1.0
  zipkin:
    tracing:
      endpoint: http://localhost:9411/api/v2/spans

logging:
  pattern:
    level: '%5p [${spring.application.name:},%X{traceId:-},%X{spanId:-}]'

// Custom Span
@Service
@Slf4j
public class PaymentService {

    private final Tracer tracer;

    public PaymentService(Tracer tracer) {
        this.tracer = tracer;
    }

    public PaymentResponse processPayment(PaymentRequest request) {
        Span span = tracer.nextSpan().name("process-payment").start();
        try (Tracer.SpanInScope ws = tracer.withSpan(span)) {
            span.tag("payment.amount", request.getAmount().toString());
            span.tag("payment.method", request.getMethod());

            log.info("Processing payment: {}", request);

            // Payment processing logic
            PaymentResponse response = executePayment(request);

            span.tag("payment.status", response.getStatus());
            return response;
        } catch (Exception e) {
            span.tag("error", e.getMessage());
            span.error(e);
            throw e;
        } finally {
            span.end();
        }
    }

    private PaymentResponse executePayment(PaymentRequest request) {
        // Implementation
        return new PaymentResponse();
    }
}

// Async Processing with Tracing
@Service
public class AsyncService {

    private final Tracer tracer;
    private final Executor executor;

    @Async
    public CompletableFuture<String> processAsync(String data) {
        Span span = tracer.currentSpan();

        return CompletableFuture.supplyAsync(() -> {
            try (Tracer.SpanInScope ws = tracer.withSpan(span)) {
                // Process data
                return "Processed: " + data;
            }
        }, executor);
    }
}
```

### Load Balancing

```java
// LoadBalancer Configuration
@Configuration
public class LoadBalancerConfig {

    @Bean
    @LoadBalanced
    public WebClient.Builder webClientBuilder() {
        return WebClient.builder();
    }

    @Bean
    @LoadBalanced
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }

    // Custom LoadBalancer Configuration
    @Bean
    public ServiceInstanceListSupplier discoveryClientServiceInstanceListSupplier(
            ConfigurableApplicationContext context) {
        return ServiceInstanceListSupplier.builder()
            .withDiscoveryClient()
            .withHealthChecks()
            .withCaching()
            .build(context);
    }
}

// Using LoadBalanced RestTemplate
@Service
public class UserClientService {

    private final RestTemplate restTemplate;

    public UserClientService(@LoadBalanced RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    public UserResponse getUserById(Long id) {
        return restTemplate.getForObject(
            "http://user-service/api/users/{id}",
            UserResponse.class,
            id
        );
    }

    public List<UserResponse> getAllUsers() {
        ResponseEntity<UserResponse[]> response = restTemplate.getForEntity(
            "http://user-service/api/users",
            UserResponse[].class
        );
        return Arrays.asList(response.getBody());
    }
}

// Using LoadBalanced WebClient
@Service
public class OrderClientService {

    private final WebClient.Builder webClientBuilder;

    public OrderClientService(WebClient.Builder webClientBuilder) {
        this.webClientBuilder = webClientBuilder;
    }

    public Mono<OrderResponse> createOrder(OrderRequest request) {
        return webClientBuilder.build()
            .post()
            .uri("lb://order-service/api/orders")
            .bodyValue(request)
            .retrieve()
            .bodyToMono(OrderResponse.class);
    }

    public Flux<OrderResponse> getOrdersByUserId(Long userId) {
        return webClientBuilder.build()
            .get()
            .uri("lb://order-service/api/orders?userId={userId}", userId)
            .retrieve()
            .bodyToFlux(OrderResponse.class);
    }
}
```

### Feign Client

```java
// Enable Feign Clients
@SpringBootApplication
@EnableFeignClients
public class OrderServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(OrderServiceApplication.class, args);
    }
}

// Feign Client Interface
@FeignClient(
    name = "user-service",
    fallback = UserServiceFallback.class,
    configuration = FeignConfig.class
)
public interface UserServiceClient {

    @GetMapping("/api/users/{id}")
    UserResponse getUserById(@PathVariable("id") Long id);

    @GetMapping("/api/users")
    List<UserResponse> getAllUsers(
        @RequestParam(required = false) String search,
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size
    );

    @PostMapping("/api/users")
    UserResponse createUser(@RequestBody UserRequest request);

    @PutMapping("/api/users/{id}")
    UserResponse updateUser(
        @PathVariable("id") Long id,
        @RequestBody UserRequest request
    );

    @DeleteMapping("/api/users/{id}")
    void deleteUser(@PathVariable("id") Long id);
}

// Feign Configuration
@Configuration
public class FeignConfig {

    @Bean
    public RequestInterceptor requestInterceptor() {
        return requestTemplate -> {
            requestTemplate.header("X-Service-Name", "order-service");
            requestTemplate.header("X-Request-Id", UUID.randomUUID().toString());
        };
    }

    @Bean
    public ErrorDecoder errorDecoder() {
        return new CustomErrorDecoder();
    }

    @Bean
    public Logger.Level feignLoggerLevel() {
        return Logger.Level.FULL;
    }

    @Bean
    public Retryer retryer() {
        return new Retryer.Default(100, 1000, 3);
    }
}

// Custom Error Decoder
public class CustomErrorDecoder implements ErrorDecoder {

    private final ErrorDecoder defaultErrorDecoder = new Default();

    @Override
    public Exception decode(String methodKey, Response response) {
        if (response.status() == 404) {
            return new ResourceNotFoundException("Resource not found");
        }
        if (response.status() == 400) {
            return new BadRequestException("Bad request");
        }
        return defaultErrorDecoder.decode(methodKey, response);
    }
}

// Fallback Implementation
@Component
public class UserServiceFallback implements UserServiceClient {

    @Override
    public UserResponse getUserById(Long id) {
        return UserResponse.builder()
            .id(id)
            .username("Unknown")
            .email("unavailable@example.com")
            .build();
    }

    @Override
    public List<UserResponse> getAllUsers(String search, int page, int size) {
        return Collections.emptyList();
    }

    @Override
    public UserResponse createUser(UserRequest request) {
        throw new ServiceUnavailableException("User service is unavailable");
    }

    @Override
    public UserResponse updateUser(Long id, UserRequest request) {
        throw new ServiceUnavailableException("User service is unavailable");
    }

    @Override
    public void deleteUser(Long id) {
        throw new ServiceUnavailableException("User service is unavailable");
    }
}

// Using Feign Client
@Service
public class OrderService {

    private final UserServiceClient userServiceClient;

    public OrderService(UserServiceClient userServiceClient) {
        this.userServiceClient = userServiceClient;
    }

    public OrderResponse createOrder(OrderRequest request) {
        // Get user details
        UserResponse user = userServiceClient.getUserById(request.getUserId());

        // Create order
        Order order = Order.builder()
            .userId(user.getId())
            .totalAmount(request.getTotalAmount())
            .status(OrderStatus.PENDING)
            .build();

        // Save and return
        return OrderResponse.from(order);
    }
}
```

### Message-Driven Microservices

```java
// Spring Cloud Stream with Kafka
@SpringBootApplication
@EnableBinding(MessageChannels.class)
public class NotificationServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(NotificationServiceApplication.class, args);
    }
}

// Message Channels
public interface MessageChannels {
    String ORDER_CREATED = "order-created-in";
    String ORDER_UPDATED = "order-updated-in";
    String NOTIFICATION_OUT = "notification-out";

    @Input(ORDER_CREATED)
    SubscribableChannel orderCreatedInput();

    @Input(ORDER_UPDATED)
    SubscribableChannel orderUpdatedInput();

    @Output(NOTIFICATION_OUT)
    MessageChannel notificationOutput();
}

// Message Listener
@Component
@Slf4j
public class OrderEventListener {

    private final NotificationService notificationService;

    public OrderEventListener(NotificationService notificationService) {
        this.notificationService = notificationService;
    }

    @StreamListener(MessageChannels.ORDER_CREATED)
    public void handleOrderCreated(OrderCreatedEvent event) {
        log.info("Received order created event: {}", event);
        notificationService.sendOrderConfirmation(event);
    }

    @StreamListener(MessageChannels.ORDER_UPDATED)
    public void handleOrderUpdated(OrderUpdatedEvent event) {
        log.info("Received order updated event: {}", event);
        notificationService.sendOrderUpdate(event);
    }
}

// Message Publisher
@Service
public class EventPublisher {

    private final MessageChannels messageChannels;

    public EventPublisher(MessageChannels messageChannels) {
        this.messageChannels = messageChannels;
    }

    public void publishNotification(NotificationEvent event) {
        Message<NotificationEvent> message = MessageBuilder
            .withPayload(event)
            .setHeader("event-type", event.getType())
            .setHeader("correlation-id", UUID.randomUUID().toString())
            .build();

        messageChannels.notificationOutput().send(message);
    }
}

// application.yml
spring:
  cloud:
    stream:
      kafka:
        binder:
          brokers: localhost:9092
          auto-add-partitions: true
          auto-create-topics: true
      bindings:
        order-created-in:
          destination: order-events
          group: notification-service
          content-type: application/json
          consumer:
            max-attempts: 3
            back-off-initial-interval: 1000
            back-off-max-interval: 10000
            back-off-multiplier: 2.0
        order-updated-in:
          destination: order-events
          group: notification-service
          content-type: application/json
        notification-out:
          destination: notification-events
          content-type: application/json
          producer:
            partition-count: 3
```

## Architecture Patterns

### Saga Pattern (Orchestration)

```java
// Saga Orchestrator
@Service
@Slf4j
public class OrderSagaOrchestrator {

    private final OrderService orderService;
    private final PaymentService paymentService;
    private final InventoryService inventoryService;
    private final ShippingService shippingService;

    public OrderResponse executeOrderSaga(OrderRequest request) {
        Order order = null;
        Payment payment = null;
        Reservation reservation = null;

        try {
            // Step 1: Create Order
            order = orderService.createOrder(request);
            log.info("Order created: {}", order.getId());

            // Step 2: Reserve Inventory
            reservation = inventoryService.reserveItems(order.getItems());
            log.info("Inventory reserved: {}", reservation.getId());

            // Step 3: Process Payment
            payment = paymentService.processPayment(
                order.getId(),
                order.getTotalAmount()
            );
            log.info("Payment processed: {}", payment.getId());

            // Step 4: Arrange Shipping
            shippingService.arrangeShipping(order.getId());
            log.info("Shipping arranged for order: {}", order.getId());

            // Step 5: Complete Order
            order = orderService.completeOrder(order.getId());
            log.info("Order completed: {}", order.getId());

            return OrderResponse.from(order);

        } catch (Exception e) {
            log.error("Saga failed, initiating compensation", e);
            compensate(order, payment, reservation);
            throw new SagaFailedException("Order processing failed", e);
        }
    }

    private void compensate(Order order, Payment payment, Reservation reservation) {
        // Compensate in reverse order
        if (payment != null) {
            try {
                paymentService.refundPayment(payment.getId());
                log.info("Payment refunded: {}", payment.getId());
            } catch (Exception e) {
                log.error("Failed to refund payment", e);
            }
        }

        if (reservation != null) {
            try {
                inventoryService.releaseReservation(reservation.getId());
                log.info("Inventory reservation released: {}", reservation.getId());
            } catch (Exception e) {
                log.error("Failed to release inventory", e);
            }
        }

        if (order != null) {
            try {
                orderService.cancelOrder(order.getId());
                log.info("Order cancelled: {}", order.getId());
            } catch (Exception e) {
                log.error("Failed to cancel order", e);
            }
        }
    }
}
```

### CQRS Pattern

```java
// Command Side
@Service
public class OrderCommandService {

    private final OrderRepository orderRepository;
    private final EventPublisher eventPublisher;

    public OrderResponse createOrder(CreateOrderCommand command) {
        Order order = Order.builder()
            .userId(command.getUserId())
            .items(command.getItems())
            .totalAmount(calculateTotal(command.getItems()))
            .status(OrderStatus.PENDING)
            .build();

        order = orderRepository.save(order);

        // Publish event
        eventPublisher.publish(new OrderCreatedEvent(order));

        return OrderResponse.from(order);
    }

    public void updateOrderStatus(UpdateOrderStatusCommand command) {
        Order order = orderRepository.findById(command.getOrderId())
            .orElseThrow(() -> new ResourceNotFoundException("Order not found"));

        order.setStatus(command.getStatus());
        orderRepository.save(order);

        // Publish event
        eventPublisher.publish(new OrderStatusUpdatedEvent(order));
    }
}

// Query Side
@Service
public class OrderQueryService {

    private final OrderReadRepository orderReadRepository;

    public OrderView getOrderById(Long orderId) {
        return orderReadRepository.findById(orderId)
            .orElseThrow(() -> new ResourceNotFoundException("Order not found"));
    }

    public Page<OrderView> getOrdersByUserId(Long userId, Pageable pageable) {
        return orderReadRepository.findByUserId(userId, pageable);
    }

    public List<OrderView> getOrdersByStatus(OrderStatus status) {
        return orderReadRepository.findByStatus(status);
    }
}

// Read Model Projection
@Component
public class OrderProjection {

    private final OrderReadRepository orderReadRepository;

    @EventListener
    public void on(OrderCreatedEvent event) {
        OrderView view = OrderView.builder()
            .orderId(event.getOrderId())
            .userId(event.getUserId())
            .totalAmount(event.getTotalAmount())
            .status(event.getStatus())
            .createdAt(event.getCreatedAt())
            .build();

        orderReadRepository.save(view);
    }

    @EventListener
    public void on(OrderStatusUpdatedEvent event) {
        orderReadRepository.findById(event.getOrderId())
            .ifPresent(view -> {
                view.setStatus(event.getStatus());
                view.setUpdatedAt(event.getUpdatedAt());
                orderReadRepository.save(view);
            });
    }
}
```

## Best Practices

1. **Use service discovery for dynamic service registration**
2. **Implement circuit breakers for all external service calls**
3. **Use API Gateway as single entry point**
4. **Centralize configuration with Config Server**
5. **Implement distributed tracing for observability**
6. **Use asynchronous communication where possible**
7. **Implement proper error handling and fallbacks**
8. **Use correlation IDs for request tracking**
9. **Implement health checks for all services**
10. **Use bulkhead pattern to isolate failures**
11. **Implement retry with exponential backoff**
12. **Use event-driven architecture for loose coupling**
13. **Implement proper security at gateway level**
14. **Use database per service pattern**
15. **Implement saga pattern for distributed transactions**

## Production Checklist

- [ ] Service discovery configured and tested
- [ ] API Gateway with proper routing
- [ ] Circuit breakers on all service calls
- [ ] Distributed tracing enabled
- [ ] Centralized logging configured
- [ ] Configuration externalized
- [ ] Health checks implemented
- [ ] Metrics and monitoring setup
- [ ] Rate limiting configured
- [ ] Authentication/authorization at gateway
- [ ] Database migrations per service
- [ ] Event-driven communication implemented
- [ ] Saga/compensation logic for transactions
- [ ] Proper timeout configuration
- [ ] Service mesh evaluated (if needed)
- [ ] Container orchestration ready
- [ ] Secrets management configured
- [ ] Backup and disaster recovery plan
- [ ] Load testing completed
- [ ] Chaos engineering tested

## Quick Reference

```bash
# Start Eureka Server
java -jar eureka-server.jar

# Start Config Server
java -jar config-server.jar

# Start Service with specific profile
java -jar -Dspring.profiles.active=prod user-service.jar

# Refresh configuration
curl -X POST http://localhost:8080/actuator/refresh

# Check Eureka registered services
curl http://localhost:8761/eureka/apps

# Zipkin UI
http://localhost:9411/zipkin/
```

## Pro Tips

1. Use Spring Cloud LoadBalancer instead of deprecated Ribbon
2. Implement health indicators for downstream dependencies
3. Use WebClient over RestTemplate for reactive support
4. Configure proper timeouts at all levels
5. Use correlation IDs for request tracing
6. Implement proper service versioning
7. Use feature toggles for gradual rollouts
8. Monitor circuit breaker metrics
9. Implement proper retry strategies
10. Use contract testing between services

## Common Mistakes to Avoid

1. Not implementing circuit breakers
2. Synchronous communication everywhere
3. Shared databases between services
4. No distributed tracing
5. Hardcoded service URLs
6. No proper error handling
7. Missing health checks
8. No timeouts configured
9. Ignoring network latency
10. No service versioning strategy
11. Insufficient monitoring
12. No chaos engineering
13. Ignoring eventual consistency
14. Not planning for failures
15. Monolithic database in microservices
