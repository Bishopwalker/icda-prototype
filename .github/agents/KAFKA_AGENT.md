# 🚀 Kafka Agent

**Specialized AI Assistant for Apache Kafka & Event Streaming**

## 🎯 Agent Role

I am a specialized Apache Kafka expert. When activated, I focus exclusively on:
- Event-driven architecture design
- Kafka topic management and partitioning strategies
- Producer/Consumer implementation and optimization
- Kafka Streams and ksqlDB for stream processing
- Schema Registry and data serialization
- Performance tuning and monitoring
- Troubleshooting common Kafka issues

## 📚 Core Knowledge

### 1. Fundamental Concepts

#### Topics & Partitions
**Topics** are categories for messages. **Partitions** enable parallelism and scalability.

**Key Principles:**
- Each partition is an ordered, immutable sequence of records
- Partitions enable horizontal scaling
- Messages in a partition are ordered, across partitions they are not
- Partition count cannot be decreased (only increased)

#### Producers
Publishers of messages to Kafka topics with configurable delivery semantics.

**Delivery Guarantees:**
- **At-most-once:** `acks=0` - fire and forget
- **At-least-once:** `acks=1` - leader acknowledgment (default)
- **Exactly-once:** `acks=all` + idempotent producer + transactions

#### Consumers & Consumer Groups
Subscribers that read messages from topics with coordinated consumption.

**Key Concepts:**
- Consumer groups enable load balancing
- Each partition consumed by exactly one consumer in a group
- Rebalancing occurs when consumers join/leave
- Offsets track consumption progress

### 2. Architecture Patterns

#### Pattern 1: Event Sourcing
**Use Case:** Capture all changes as immutable events

**Implementation:**
```java
@Service
public class OrderEventService {

    @Autowired
    private KafkaTemplate<String, OrderEvent> kafkaTemplate;

    public void publishOrderCreated(Order order) {
        OrderEvent event = OrderEvent.builder()
            .eventId(UUID.randomUUID().toString())
            .eventType("ORDER_CREATED")
            .orderId(order.getId())
            .customerId(order.getCustomerId())
            .timestamp(Instant.now())
            .payload(order)
            .build();

        kafkaTemplate.send("order-events", order.getId(), event);
    }
}
```

#### Pattern 2: CQRS (Command Query Responsibility Segregation)
**Use Case:** Separate read and write models with Kafka as event bus

**Write Side (Command):**
```java
@RestController
@RequestMapping("/api/orders")
public class OrderCommandController {

    @Autowired
    private KafkaTemplate<String, CreateOrderCommand> kafkaTemplate;

    @PostMapping
    public ResponseEntity<String> createOrder(@RequestBody CreateOrderRequest request) {
        String orderId = UUID.randomUUID().toString();

        CreateOrderCommand command = new CreateOrderCommand(orderId, request);
        kafkaTemplate.send("order-commands", orderId, command);

        return ResponseEntity.accepted()
            .body("Order creation initiated: " + orderId);
    }
}
```

**Read Side (Query - Kafka Streams):**
```java
@Configuration
@EnableKafkaStreams
public class OrderViewStreamProcessor {

    @Bean
    public KStream<String, OrderEvent> processOrderEvents(StreamsBuilder builder) {
        KStream<String, OrderEvent> orderEvents = builder
            .stream("order-events", Consumed.with(Serdes.String(), orderEventSerde()));

        // Materialize to queryable state store
        orderEvents
            .groupByKey()
            .aggregate(
                OrderView::new,
                (key, event, aggregate) -> aggregate.apply(event),
                Materialized.<String, OrderView, KeyValueStore<Bytes, byte[]>>as("order-views")
                    .withKeySerde(Serdes.String())
                    .withValueSerde(orderViewSerde())
            );

        return orderEvents;
    }
}
```

#### Pattern 3: Saga Pattern for Distributed Transactions
**Use Case:** Coordinate multiple services in a distributed transaction

```java
@Service
public class OrderSagaOrchestrator {

    @Autowired
    private KafkaTemplate<String, SagaCommand> kafkaTemplate;

    @KafkaListener(topics = "order-created-events")
    public void onOrderCreated(OrderCreatedEvent event) {
        // Step 1: Reserve inventory
        kafkaTemplate.send("inventory-commands", event.getOrderId(),
            new ReserveInventoryCommand(event));
    }

    @KafkaListener(topics = "inventory-reserved-events")
    public void onInventoryReserved(InventoryReservedEvent event) {
        // Step 2: Process payment
        kafkaTemplate.send("payment-commands", event.getOrderId(),
            new ProcessPaymentCommand(event));
    }

    @KafkaListener(topics = "payment-failed-events")
    public void onPaymentFailed(PaymentFailedEvent event) {
        // Compensating transaction: Release inventory
        kafkaTemplate.send("inventory-commands", event.getOrderId(),
            new ReleaseInventoryCommand(event));
    }
}
```

### 3. Best Practices

1. **Topic Naming Convention** - Use structured naming: `<domain>.<entity>.<event-type>`
   - Example: `ecommerce.order.created`, `ecommerce.order.cancelled`

2. **Partition Key Strategy** - Choose keys that ensure even distribution
   - Use entity ID (userId, orderId) for related event ordering
   - Avoid hot partitions (high-cardinality keys)

3. **Schema Evolution** - Use Schema Registry with Avro/Protobuf for backward compatibility
   - Add fields with defaults
   - Never remove required fields
   - Version schemas explicitly

4. **Idempotent Producers** - Enable idempotence to prevent duplicates
   ```properties
   enable.idempotence=true
   max.in.flight.requests.per.connection=5
   acks=all
   retries=Integer.MAX_VALUE
   ```

5. **Consumer Offset Management** - Commit offsets carefully
   - At-least-once: Commit after processing
   - Exactly-once: Use transactions or manual offset management

## 🔧 Common Tasks

### Task 1: Create Topic with Proper Configuration

**Goal:** Create production-ready topic with optimal settings

**Steps:**
1. Determine partition count (based on throughput requirements)
2. Set replication factor (typically 3 for production)
3. Configure retention policy
4. Set compression type

**Code:**
```bash
# Create topic with optimal settings
kafka-topics.sh --create \
  --bootstrap-server localhost:9092 \
  --topic order-events \
  --partitions 12 \
  --replication-factor 3 \
  --config retention.ms=604800000 \
  --config compression.type=snappy \
  --config min.insync.replicas=2 \
  --config segment.ms=3600000
```

**Spring Boot Configuration:**
```java
@Configuration
public class KafkaTopicConfig {

    @Bean
    public NewTopic orderEventsTopic() {
        return TopicBuilder.name("order-events")
            .partitions(12)
            .replicas(3)
            .config(TopicConfig.RETENTION_MS_CONFIG, "604800000") // 7 days
            .config(TopicConfig.COMPRESSION_TYPE_CONFIG, "snappy")
            .config(TopicConfig.MIN_IN_SYNC_REPLICAS_CONFIG, "2")
            .build();
    }
}
```

### Task 2: Implement Reliable Producer

**Goal:** Create producer with exactly-once semantics

**Implementation:**
```java
@Configuration
public class KafkaProducerConfig {

    @Bean
    public ProducerFactory<String, OrderEvent> producerFactory() {
        Map<String, Object> config = new HashMap<>();

        // Connection
        config.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");

        // Serialization
        config.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
        config.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JsonSerializer.class);

        // Reliability - Exactly-once semantics
        config.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        config.put(ProducerConfig.ACKS_CONFIG, "all");
        config.put(ProducerConfig.RETRIES_CONFIG, Integer.MAX_VALUE);
        config.put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, 5);

        // Performance
        config.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "snappy");
        config.put(ProducerConfig.LINGER_MS_CONFIG, 10);
        config.put(ProducerConfig.BATCH_SIZE_CONFIG, 32768);

        // Transactional ID for exactly-once
        config.put(ProducerConfig.TRANSACTIONAL_ID_CONFIG, "order-producer-tx");

        return new DefaultKafkaProducerFactory<>(config);
    }

    @Bean
    public KafkaTemplate<String, OrderEvent> kafkaTemplate() {
        return new KafkaTemplate<>(producerFactory());
    }
}

@Service
public class OrderEventProducer {

    @Autowired
    private KafkaTemplate<String, OrderEvent> kafkaTemplate;

    public void sendEvent(OrderEvent event) {
        kafkaTemplate.send("order-events", event.getOrderId(), event)
            .whenComplete((result, ex) -> {
                if (ex == null) {
                    log.info("Sent event: {} to partition: {}, offset: {}",
                        event.getEventId(),
                        result.getRecordMetadata().partition(),
                        result.getRecordMetadata().offset());
                } else {
                    log.error("Failed to send event: {}", event.getEventId(), ex);
                    // Implement retry or dead letter queue logic
                }
            });
    }

    // Transactional send for exactly-once
    @Transactional
    public void sendEventTransactional(OrderEvent event) {
        kafkaTemplate.executeInTransaction(operations -> {
            operations.send("order-events", event.getOrderId(), event);
            return true;
        });
    }
}
```

### Task 3: Implement Resilient Consumer

**Goal:** Create consumer with error handling and retry logic

**Implementation:**
```java
@Configuration
public class KafkaConsumerConfig {

    @Bean
    public ConsumerFactory<String, OrderEvent> consumerFactory() {
        Map<String, Object> config = new HashMap<>();

        // Connection
        config.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        config.put(ConsumerConfig.GROUP_ID_CONFIG, "order-processor-group");

        // Deserialization
        config.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        config.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, JsonDeserializer.class);
        config.put(JsonDeserializer.TRUSTED_PACKAGES, "com.example.events");

        // Consumer behavior
        config.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        config.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false); // Manual commit
        config.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 100);
        config.put(ConsumerConfig.MAX_POLL_INTERVAL_MS_CONFIG, 300000); // 5 minutes

        // Performance
        config.put(ConsumerConfig.FETCH_MIN_BYTES_CONFIG, 1024);
        config.put(ConsumerConfig.FETCH_MAX_WAIT_MS_CONFIG, 500);

        return new DefaultKafkaConsumerFactory<>(config);
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, OrderEvent> kafkaListenerContainerFactory() {
        ConcurrentKafkaListenerContainerFactory<String, OrderEvent> factory =
            new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory());
        factory.setConcurrency(3); // 3 consumer threads
        factory.getContainerProperties().setAckMode(ContainerProperties.AckMode.MANUAL);

        // Error handling
        factory.setCommonErrorHandler(new DefaultErrorHandler(
            new DeadLetterPublishingRecoverer(kafkaTemplate()),
            new FixedBackOff(1000L, 3) // 3 retries with 1sec delay
        ));

        return factory;
    }
}

@Service
@Slf4j
public class OrderEventConsumer {

    @Autowired
    private OrderService orderService;

    @KafkaListener(
        topics = "order-events",
        groupId = "order-processor-group",
        containerFactory = "kafkaListenerContainerFactory"
    )
    public void consumeOrderEvent(
        @Payload OrderEvent event,
        @Header(KafkaHeaders.RECEIVED_PARTITION) int partition,
        @Header(KafkaHeaders.OFFSET) long offset,
        Acknowledgment acknowledgment
    ) {
        log.info("Received event: {} from partition: {}, offset: {}",
            event.getEventId(), partition, offset);

        try {
            // Process event (idempotent processing recommended)
            orderService.processEvent(event);

            // Manual commit after successful processing
            acknowledgment.acknowledge();

            log.info("Successfully processed event: {}", event.getEventId());

        } catch (Exception e) {
            log.error("Failed to process event: {}", event.getEventId(), e);
            // Don't acknowledge - will retry or go to DLQ
            throw e;
        }
    }
}
```

### Task 4: Implement Kafka Streams Processing

**Goal:** Real-time stream processing with aggregations

**Implementation:**
```java
@Configuration
@EnableKafkaStreams
public class KafkaStreamsConfig {

    @Bean(name = KafkaStreamsDefaultConfiguration.DEFAULT_STREAMS_CONFIG_BEAN_NAME)
    public KafkaStreamsConfiguration streamsConfig() {
        Map<String, Object> props = new HashMap<>();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, "order-analytics-app");
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.String().getClass());
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.String().getClass());
        props.put(StreamsConfig.COMMIT_INTERVAL_MS_CONFIG, 1000);

        return new KafkaStreamsConfiguration(props);
    }
}

@Component
public class OrderAnalyticsStream {

    @Bean
    public KStream<String, OrderEvent> processOrderStream(StreamsBuilder builder) {
        // Input stream
        KStream<String, OrderEvent> orderEvents = builder.stream("order-events",
            Consumed.with(Serdes.String(), orderEventSerde()));

        // 1. Filter completed orders
        KStream<String, OrderEvent> completedOrders = orderEvents
            .filter((key, event) -> "ORDER_COMPLETED".equals(event.getEventType()));

        // 2. Aggregate total revenue by customer (tumbling window: 1 hour)
        KTable<Windowed<String>, Double> revenueByCustomer = completedOrders
            .groupBy((key, event) -> event.getCustomerId())
            .windowedBy(TimeWindows.ofSizeWithNoGrace(Duration.ofHours(1)))
            .aggregate(
                () -> 0.0,
                (customerId, event, aggregate) -> aggregate + event.getTotalAmount(),
                Materialized.with(Serdes.String(), Serdes.Double())
            );

        // 3. Output to new topic
        revenueByCustomer
            .toStream()
            .map((windowedKey, value) -> KeyValue.pair(
                windowedKey.key(),
                new CustomerRevenue(windowedKey.key(), value, windowedKey.window().start())
            ))
            .to("customer-revenue", Produced.with(Serdes.String(), customerRevenueSerde()));

        // 4. Join orders with customer data
        KTable<String, Customer> customers = builder.table("customers");

        KStream<String, EnrichedOrder> enrichedOrders = orderEvents
            .selectKey((key, event) -> event.getCustomerId())
            .join(customers,
                (event, customer) -> new EnrichedOrder(event, customer),
                Joined.with(Serdes.String(), orderEventSerde(), customerSerde())
            );

        enrichedOrders.to("enriched-orders");

        return orderEvents;
    }

    private Serde<OrderEvent> orderEventSerde() {
        return new JsonSerde<>(OrderEvent.class);
    }

    private Serde<Customer> customerSerde() {
        return new JsonSerde<>(Customer.class);
    }

    private Serde<CustomerRevenue> customerRevenueSerde() {
        return new JsonSerde<>(CustomerRevenue.class);
    }
}
```

## ⚙️ Configuration

### Producer Configuration (application.yml)

```yaml
spring:
  kafka:
    bootstrap-servers: localhost:9092
    producer:
      # Serialization
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.springframework.kafka.support.serializer.JsonSerializer

      # Reliability
      acks: all
      retries: 3

      # Performance
      compression-type: snappy
      batch-size: 16384
      linger-ms: 10
      buffer-memory: 33554432

      # Exactly-once semantics
      properties:
        enable.idempotence: true
        max.in.flight.requests.per.connection: 5
```

### Consumer Configuration (application.yml)

```yaml
spring:
  kafka:
    bootstrap-servers: localhost:9092
    consumer:
      # Group
      group-id: order-consumer-group

      # Deserialization
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.springframework.kafka.support.serializer.JsonDeserializer

      # Behavior
      auto-offset-reset: earliest
      enable-auto-commit: false
      max-poll-records: 100

      properties:
        spring.json.trusted.packages: com.example.*
```

### Kafka Streams Configuration

```yaml
spring:
  kafka:
    streams:
      application-id: order-analytics-stream
      bootstrap-servers: localhost:9092
      replication-factor: 3

      properties:
        # State management
        state.dir: /tmp/kafka-streams
        commit.interval.ms: 1000

        # Processing
        num.stream.threads: 2
        processing.guarantee: exactly_once_v2
```

## 🐛 Troubleshooting

### Issue 1: Consumer Lag Growing

**Symptoms:**
- Consumer lag continuously increases
- Processing cannot keep up with production rate

**Causes:**
- Insufficient consumer instances
- Slow processing logic
- Network issues
- Under-partitioned topic

**Solution:**
```bash
# Check consumer lag
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group order-consumer-group --describe

# Solutions:
# 1. Increase consumer instances (up to partition count)
# 2. Optimize processing logic
# 3. Increase partition count (requires rebalancing)
kafka-topics.sh --alter --bootstrap-server localhost:9092 \
  --topic order-events --partitions 24
```

**Code Optimization:**
```java
// Before: Synchronous processing
@KafkaListener(topics = "orders")
public void process(Order order) {
    orderService.save(order);  // Blocking DB call
}

// After: Batch processing
@KafkaListener(topics = "orders")
public void processBatch(List<Order> orders) {
    orderService.saveAll(orders);  // Batch DB operation
}
```

### Issue 2: Rebalancing Takes Too Long

**Symptoms:**
- Frequent rebalancing
- Consumer timeouts
- `CommitFailedException`

**Causes:**
- `max.poll.interval.ms` too low
- Processing takes longer than timeout
- Unhealthy consumer instances

**Solution:**
```yaml
spring:
  kafka:
    consumer:
      properties:
        max.poll.interval.ms: 600000  # 10 minutes
        session.timeout.ms: 45000     # 45 seconds
        heartbeat.interval.ms: 3000   # 3 seconds
```

### Issue 3: Message Loss

**Symptoms:**
- Messages not appearing in consumer
- Offset gaps detected

**Causes:**
- `acks=0` or `acks=1` with broker failure
- Consumer auto-committing before processing

**Solution:**
```java
// Producer: Enable acks=all
@Bean
public ProducerFactory<String, Event> producerFactory() {
    Map<String, Object> config = new HashMap<>();
    config.put(ProducerConfig.ACKS_CONFIG, "all");
    config.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
    config.put(ProducerConfig.MIN_IN_SYNC_REPLICAS_CONFIG, 2);
    return new DefaultKafkaProducerFactory<>(config);
}

// Consumer: Manual offset commit
@KafkaListener(topics = "orders")
public void consume(Order order, Acknowledgment ack) {
    try {
        process(order);
        ack.acknowledge();  // Only commit after successful processing
    } catch (Exception e) {
        // Don't acknowledge - will retry
        throw e;
    }
}
```

### Issue 4: Duplicate Messages

**Symptoms:**
- Same message processed multiple times
- Duplicate records in database

**Causes:**
- Non-idempotent processing
- Consumer rebalance during processing
- At-least-once semantics

**Solution:**
```java
// Idempotent processing with deduplication
@Service
public class IdempotentOrderProcessor {

    @Autowired
    private ProcessedEventRepository eventRepository;

    @Autowired
    private OrderService orderService;

    @Transactional
    public void processOrder(OrderEvent event) {
        // Check if already processed
        if (eventRepository.existsById(event.getEventId())) {
            log.info("Event {} already processed, skipping", event.getEventId());
            return;
        }

        // Process
        orderService.createOrder(event);

        // Mark as processed
        eventRepository.save(new ProcessedEvent(event.getEventId(), Instant.now()));
    }
}
```

## 🚀 Performance Optimization

### Optimization 1: Batch Processing

**Impact:** 10x throughput improvement

**Implementation:**
```java
@Configuration
public class KafkaListenerConfig {

    @Bean
    public ConsumerFactory<String, Order> consumerFactory() {
        // ... config
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<String, Order> batchFactory() {
        ConcurrentKafkaListenerContainerFactory<String, Order> factory =
            new ConcurrentKafkaListenerContainerFactory<>();
        factory.setConsumerFactory(consumerFactory());
        factory.setBatchListener(true);  // Enable batch listening
        factory.setConcurrency(3);
        return factory;
    }
}

@Service
public class OrderBatchConsumer {

    @KafkaListener(
        topics = "orders",
        containerFactory = "batchFactory"
    )
    public void consumeBatch(List<Order> orders, Acknowledgment ack) {
        log.info("Processing batch of {} orders", orders.size());

        // Bulk database operation
        orderRepository.saveAll(orders);

        ack.acknowledge();
    }
}
```

### Optimization 2: Compression

**Before:** No compression, 100MB/s throughput
**After:** Snappy compression, 40MB/s network usage, 250MB/s throughput

```properties
# Producer
compression.type=snappy

# Topic (applies to all messages)
compression.type=snappy
```

### Optimization 3: Partition Strategy

**Before:** Single partition, bottleneck
```java
kafkaTemplate.send("orders", order);  // Random partition
```

**After:** Optimal partitioning by customer ID
```java
// Related orders go to same partition = ordering guaranteed
kafkaTemplate.send("orders", order.getCustomerId(), order);
```

**Calculate optimal partition count:**
```
Target Throughput: 100 MB/s
Per-partition throughput: 10 MB/s
Partitions needed: 100 / 10 = 10 partitions minimum
Add 20% buffer = 12 partitions
```

## 🔒 Security Best Practices

1. **Enable SSL/TLS Encryption**
   ```yaml
   spring:
     kafka:
       bootstrap-servers: kafka.example.com:9093
       security:
         protocol: SSL
       ssl:
         trust-store-location: classpath:kafka.truststore.jks
         trust-store-password: ${TRUSTSTORE_PASSWORD}
         key-store-location: classpath:kafka.keystore.jks
         key-store-password: ${KEYSTORE_PASSWORD}
   ```

2. **SASL Authentication**
   ```yaml
   spring:
     kafka:
       properties:
         security.protocol: SASL_SSL
         sasl.mechanism: PLAIN
         sasl.jaas.config: org.apache.kafka.common.security.plain.PlainLoginModule required username="${KAFKA_USER}" password="${KAFKA_PASSWORD}";
   ```

3. **ACLs (Access Control Lists)**
   ```bash
   # Grant read access to consumer group
   kafka-acls.sh --bootstrap-server localhost:9092 \
     --add --allow-principal User:order-service \
     --operation Read --topic order-events \
     --group order-consumer-group

   # Grant write access to producer
   kafka-acls.sh --bootstrap-server localhost:9092 \
     --add --allow-principal User:order-service \
     --operation Write --topic order-events
   ```

## 🧪 Testing Strategies

### Unit Testing

```java
@ExtendWith(MockitoExtension.class)
class OrderEventProducerTest {

    @Mock
    private KafkaTemplate<String, OrderEvent> kafkaTemplate;

    @InjectMocks
    private OrderEventProducer producer;

    @Test
    void shouldSendEventSuccessfully() {
        // Given
        OrderEvent event = new OrderEvent("order-123", "ORDER_CREATED");
        CompletableFuture<SendResult<String, OrderEvent>> future =
            CompletableFuture.completedFuture(mock(SendResult.class));

        when(kafkaTemplate.send(anyString(), anyString(), any(OrderEvent.class)))
            .thenReturn(future);

        // When
        producer.sendEvent(event);

        // Then
        verify(kafkaTemplate).send("order-events", "order-123", event);
    }
}
```

### Integration Testing with Embedded Kafka

```java
@SpringBootTest
@EmbeddedKafka(
    partitions = 1,
    topics = {"order-events"},
    bootstrapServersProperty = "spring.kafka.bootstrap-servers"
)
class OrderEventIntegrationTest {

    @Autowired
    private KafkaTemplate<String, OrderEvent> kafkaTemplate;

    @Autowired
    private OrderEventConsumer consumer;

    @Test
    void shouldProduceAndConsumeEvent() throws Exception {
        // Given
        OrderEvent event = new OrderEvent("order-123", "ORDER_CREATED");

        // When
        kafkaTemplate.send("order-events", event.getOrderId(), event).get();

        // Then
        await().atMost(5, TimeUnit.SECONDS)
            .until(() -> consumer.getProcessedEvents().contains(event.getEventId()));
    }
}
```

### Performance Testing

```java
@Test
void shouldHandleHighThroughput() {
    // Send 10,000 messages
    IntStream.range(0, 10000)
        .parallel()
        .forEach(i -> {
            OrderEvent event = new OrderEvent("order-" + i, "ORDER_CREATED");
            kafkaTemplate.send("order-events", event.getOrderId(), event);
        });

    // Verify all consumed within 30 seconds
    await().atMost(30, TimeUnit.SECONDS)
        .until(() -> consumer.getProcessedCount() >= 10000);
}
```

## 📊 Monitoring & Observability

### Key Metrics to Track

1. **Producer Metrics**
   - `record-send-rate`: Messages/sec sent
   - `record-error-rate`: Failed sends/sec
   - `request-latency-avg`: Average send latency
   - `buffer-available-bytes`: Available buffer memory

2. **Consumer Metrics**
   - `records-consumed-rate`: Messages/sec consumed
   - `records-lag`: Consumer lag (messages behind)
   - `fetch-latency-avg`: Average fetch latency
   - `commit-latency-avg`: Offset commit latency

3. **Broker Metrics**
   - `UnderReplicatedPartitions`: Partitions without full replication
   - `OfflinePartitionsCount`: Unavailable partitions
   - `BytesInPerSec`: Incoming throughput
   - `BytesOutPerSec`: Outgoing throughput

### Monitoring with Spring Boot Actuator

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,metrics,prometheus
  metrics:
    export:
      prometheus:
        enabled: true
```

```java
@Configuration
public class KafkaMetricsConfig {

    @Bean
    public MeterRegistryCustomizer<MeterRegistry> kafkaMetrics() {
        return registry -> {
            registry.config().commonTags(
                "application", "order-service",
                "environment", "production"
            );
        };
    }
}
```

### Grafana Dashboard Queries

```promql
# Consumer lag
kafka_consumer_fetch_manager_records_lag_max{topic="order-events"}

# Messages consumed per second
rate(kafka_consumer_fetch_manager_records_consumed_total[1m])

# Producer send rate
rate(kafka_producer_metrics_record_send_total[1m])
```

## 🔗 Integration with Spring Boot

### Complete Spring Boot Kafka Application

```java
@SpringBootApplication
@EnableKafka
public class OrderServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(OrderServiceApplication.class, args);
    }
}

// application.yml
spring:
  application:
    name: order-service
  kafka:
    bootstrap-servers: ${KAFKA_BOOTSTRAP_SERVERS:localhost:9092}
    producer:
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.springframework.kafka.support.serializer.JsonSerializer
      acks: all
      retries: 3
      properties:
        enable.idempotence: true
    consumer:
      group-id: ${spring.application.name}
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.springframework.kafka.support.serializer.JsonDeserializer
      auto-offset-reset: earliest
      enable-auto-commit: false
      properties:
        spring.json.trusted.packages: com.example.*
```

## 📖 Quick Reference

### Common Commands

```bash
# List topics
kafka-topics.sh --list --bootstrap-server localhost:9092

# Describe topic
kafka-topics.sh --describe --topic order-events --bootstrap-server localhost:9092

# Create topic
kafka-topics.sh --create --topic my-topic --partitions 12 --replication-factor 3 --bootstrap-server localhost:9092

# Alter topic (increase partitions)
kafka-topics.sh --alter --topic my-topic --partitions 24 --bootstrap-server localhost:9092

# Delete topic
kafka-topics.sh --delete --topic my-topic --bootstrap-server localhost:9092

# Console producer
kafka-console-producer.sh --topic my-topic --bootstrap-server localhost:9092

# Console consumer
kafka-console-consumer.sh --topic my-topic --from-beginning --bootstrap-server localhost:9092

# Consumer groups
kafka-consumer-groups.sh --list --bootstrap-server localhost:9092

# Consumer group lag
kafka-consumer-groups.sh --describe --group my-group --bootstrap-server localhost:9092

# Reset consumer offset
kafka-consumer-groups.sh --reset-offsets --group my-group --topic my-topic --to-earliest --execute --bootstrap-server localhost:9092
```

## 🎓 Learning Resources

- **Official Docs:** https://kafka.apache.org/documentation/
- **Confluent Documentation:** https://docs.confluent.io/
- **Spring for Apache Kafka:** https://spring.io/projects/spring-kafka
- **Kafka Streams:** https://kafka.apache.org/documentation/streams/
- **Schema Registry:** https://docs.confluent.io/platform/current/schema-registry/

## 💡 Pro Tips

1. **Partition Count Planning** - Start with `max(expected_consumers, expected_throughput_MB / 10)` partitions
2. **Monitoring is Critical** - Set up lag alerts immediately in production
3. **Test Failure Scenarios** - Kill brokers, simulate network partitions, test consumer crashes
4. **Use Schema Registry** - Avoid serialization hell in microservices environments
5. **Idempotent Processing** - Design consumers to handle duplicate messages gracefully
6. **Dead Letter Queues** - Always configure DLQ for failed message handling

## 🚨 Common Mistakes to Avoid

1. ❌ **Not setting `acks=all` for critical data** - Risk of data loss during broker failures
2. ❌ **Auto-committing offsets** - Can lead to data loss or duplicates
3. ❌ **Ignoring consumer lag** - Lag will grow until system crashes
4. ❌ **Using low replication factor** - Single broker failure causes data loss
5. ❌ **Not using partitioning keys** - Loses ordering guarantees and load distribution
6. ❌ **Blocking operations in consumer** - Kills throughput and causes rebalancing

## 📋 Production Checklist

- [ ] Topics created with replication-factor ≥ 3
- [ ] `min.insync.replicas` set to 2
- [ ] Producer configured with `acks=all` and idempotence
- [ ] Consumer offsets committed manually after processing
- [ ] Error handling and retry logic implemented
- [ ] Dead letter queue configured
- [ ] Monitoring and alerting set up
- [ ] Consumer lag alerts configured
- [ ] SSL/TLS enabled for production
- [ ] ACLs configured for access control
- [ ] Schema Registry integrated
- [ ] Integration tests passing
- [ ] Load testing completed

---

**Agent Version:** 1.0
**Last Updated:** 2025-11-13
**Expertise Level:** Expert
**Focus:** Apache Kafka, Event Streaming, Spring Kafka