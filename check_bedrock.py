"""Quick check for Bedrock access and available models"""
import boto3
from botocore.config import Config
import json

# Configure boto3 client with extended timeout
BOTO_CONFIG = Config(
    read_timeout=3600,
    connect_timeout=60,
    retries={'max_attempts': 3}
)

def check_bedrock():
    print("=" * 60)
    print("ICDA Prototype - AWS Bedrock Access Check")
    print("=" * 60)
    
    # Check credentials
    sts = boto3.client('sts')
    try:
        identity = sts.get_caller_identity()
        print(f"\n✓ AWS Identity: {identity['Arn']}")
        print(f"  Account: {identity['Account']}")
    except Exception as e:
        print(f"\n✗ AWS credentials error: {e}")
        return
    
    # Check Bedrock access
    bedrock = boto3.client('bedrock', region_name='us-east-1')
    
    print("\n" + "-" * 60)
    print("Available Nova Models:")
    print("-" * 60)
    
    try:
        models = bedrock.list_foundation_models()
        nova_models = [m for m in models['modelSummaries'] 
                       if 'nova' in m['modelId'].lower()]
        
        if nova_models:
            for m in nova_models:
                print(f"  • {m['modelId']}")
                print(f"    Provider: {m['providerName']}")
                print(f"    Input: {m.get('inputModalities', ['N/A'])}")
                print(f"    Output: {m.get('outputModalities', ['N/A'])}")
                print()
        else:
            print("  No Nova models found. You may need to enable them in Bedrock console.")
    except Exception as e:
        print(f"  ✗ Error listing models: {e}")
    
    # Test invoke permission
    print("-" * 60)
    print("Testing Bedrock Runtime Access:")
    print("-" * 60)
    
    runtime = boto3.client('bedrock-runtime', region_name='us-east-1', config=BOTO_CONFIG)
    
    test_models = [
        'us.amazon.nova-micro-v1:0',
        'us.amazon.nova-lite-v1:0', 
        'us.amazon.nova-pro-v1:0',
        'amazon.nova-micro-v1:0',
        'amazon.nova-lite-v1:0',
        'amazon.nova-pro-v1:0'
    ]
    
    working_model = None
    for model_id in test_models:
        try:
            response = runtime.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": "Say 'hello' and nothing else."}]}],
                inferenceConfig={"maxTokens": 10}
            )
            output = response['output']['message']['content'][0]['text']
            print(f"  ✓ {model_id} - WORKS")
            print(f"    Response: {output}")
            working_model = model_id
            break
        except Exception as e:
            err = str(e)
            if 'AccessDeniedException' in err:
                print(f"  ✗ {model_id} - Access Denied (need to enable in console)")
            elif 'ResourceNotFoundException' in err:
                print(f"  - {model_id} - Not found in this region")
            else:
                print(f"  ? {model_id} - {err[:80]}")
    
    print("\n" + "=" * 60)
    if working_model:
        print(f"✓ READY TO GO! Working model: {working_model}")
        print(f"\nUpdate your .env with:")
        print(f"  NOVA_MICRO_MODEL={working_model}")
    else:
        print("✗ No working Nova models found.")
        print("\nTo enable Nova models:")
        print("  1. Go to AWS Console → Bedrock → Model access")
        print("  2. Click 'Manage model access'")
        print("  3. Enable Amazon Nova models")
        print("  4. Wait ~1 minute for propagation")
    print("=" * 60)

if __name__ == "__main__":
    check_bedrock()
