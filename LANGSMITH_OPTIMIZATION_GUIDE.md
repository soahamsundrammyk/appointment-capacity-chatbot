# LangSmith Optimization Guide for Capacity Chatbot

## 🎯 Table of Contents
1. [Setting Up Experiments](#setting-up-experiments)
2. [Key Metrics to Track](#key-metrics-to-track)
3. [Comparing ReAct vs 3 LLM Calls](#comparing-react-vs-3-llm-calls)
4. [Prompt Template Testing](#prompt-template-testing)
5. [Model Comparison](#model-comparison)
6. [Scoring & Evaluation](#scoring--evaluation)
7. [Best Practices](#best-practices)

---

## 1. Setting Up Experiments

### A. Create Different Project Names for Each Approach

In your `.env` file, use different project names to separate experiments:

```bash
# ReAct Approach
LANGCHAIN_PROJECT=capacity-chatbot-react

# 3 LLM Calls Approach (if you want to compare)
LANGCHAIN_PROJECT=capacity-chatbot-3calls

# Different Models
LANGCHAIN_PROJECT=capacity-chatbot-gpt4o
LANGCHAIN_PROJECT=capacity-chatbot-gpt4o-mini
```

### B. Use Tags to Organize Runs

Add tags to your runs for better filtering:

```python
# In capacity_agent.py, add tags to config
config_with_tags = {
    **agent_config,
    "tags": [
        "react-approach",
        "gpt-4o-mini",
        "v1.0",
        "production"
    ],
    "metadata": {
        "experiment_id": "react-vs-3calls-001",
        "model": "gpt-4o-mini",
        "approach": "react",
        "timestamp": datetime.now().isoformat()
    }
}
```

---

## 2. Key Metrics to Track

### A. Cost Metrics (Most Important for Your Use Case)

**Why**: You want to reduce from 3 LLM calls to 1.

**What to Track**:
- **Total Cost per Query**: Sum of all LLM calls
- **Tokens Used**: Input + Output tokens
- **Number of LLM Calls**: Should be 1 for ReAct, 3 for old approach
- **Cost per Token**: Model-specific pricing

**How to View in LangSmith**:
1. Go to LangSmith Dashboard
2. Click on "Traces" or "Runs"
3. Filter by your project
4. Look at the "Cost" column
5. Compare average cost between projects

**Example Comparison**:
```
ReAct Approach:
- LLM Calls: 1
- Avg Cost: $0.002 per query
- Avg Tokens: 1,500 input + 300 output = 1,800 tokens

3 LLM Calls Approach:
- LLM Calls: 3
- Avg Cost: $0.006 per query
- Avg Tokens: 4,500 input + 900 output = 5,400 tokens

Savings: 66% cost reduction! ✅
```

### B. Latency Metrics

**Why**: User experience - faster responses = better UX.

**What to Track**:
- **Total Latency**: Time from user message to final response
- **LLM Latency**: Time spent in LLM calls
- **Tool Latency**: Time spent in API calls (get_rules, get_capacity)
- **P95 Latency**: 95th percentile (handles outliers)

**How to View**:
1. LangSmith Dashboard → Traces
2. Look at "Duration" column
3. Compare P50, P95, P99 latencies

**Example**:
```
ReAct Approach:
- P50 Latency: 2.1s
- P95 Latency: 4.5s
- P99 Latency: 8.2s

3 LLM Calls Approach:
- P50 Latency: 5.8s
- P95 Latency: 12.3s
- P99 Latency: 20.1s

Improvement: 64% faster! ✅
```

### C. Quality Metrics

**Why**: Ensure ReAct doesn't sacrifice quality for speed/cost.

**What to Track**:
1. **Tool Call Accuracy**: Did it call the right tool?
2. **Response Relevance**: Does the answer match the question?
3. **Error Rate**: How often does it fail?
4. **Hallucination Rate**: Does it make up information?

**How to Measure**:
- Manual evaluation (label 100 queries)
- Automated scoring (see Section 6)
- User feedback (thumbs up/down)

---

## 3. Comparing ReAct vs 3 LLM Calls

### Step 1: Create a Test Dataset

Create a file `test_queries.json`:

```json
{
  "test_queries": [
    {
      "query": "get me tomorrow capacity",
      "expected_tool": "get_capacity",
      "expected_params": {
        "dates": ["2025-01-06"]
      },
      "category": "capacity_query"
    },
    {
      "query": "what are the rules?",
      "expected_tool": "get_rules",
      "expected_params": {},
      "category": "rules_query"
    },
    {
      "query": "show me capacity for loaner and vishal",
      "expected_tool": "get_capacity",
      "expected_params": {
        "transport_option_names": ["loaner"],
        "advisor_names": ["Vishal"]
      },
      "category": "complex_query"
    },
    {
      "query": "what is capacity?",
      "expected_tool": null,
      "expected_params": null,
      "category": "knowledge_query"
    }
  ]
}
```

### Step 2: Run Both Approaches

**Option A: Manual Testing**
1. Set `LANGCHAIN_PROJECT=capacity-chatbot-react`
2. Run all test queries through LangGraph Studio
3. Note down results
4. Switch to old approach (if you have it)
5. Run same queries
6. Compare in LangSmith

**Option B: Automated Testing Script**

Create `scripts/compare_approaches.py`:

```python
import asyncio
import json
from langsmith import Client
from capacity_chatbot.graph import graph

client = Client()

async def run_test_queries(project_name: str, queries: list):
    """Run test queries and return metrics."""
    results = []
    
    for query in queries:
        # Run query
        result = await graph.ainvoke(
            {
                "messages": [{"role": "user", "content": query["query"]}],
                "department_uuid": "your-dept-uuid",
            },
            config={
                "configurable": {"thread_id": f"test-{query['id']}"},
                "tags": [project_name],
                "metadata": {"test_query_id": query["id"]}
            }
        )
        
        # Extract metrics
        results.append({
            "query": query["query"],
            "response": result["response_message"],
            "latency": result.get("latency", 0),
            "cost": result.get("cost", 0),
            "tool_calls": result.get("tool_calls", [])
        })
    
    return results

# Run both approaches
react_results = await run_test_queries("react", test_queries)
three_call_results = await run_test_queries("3calls", test_queries)

# Compare
print("ReAct Avg Cost:", sum(r["cost"] for r in react_results) / len(react_results))
print("3 Calls Avg Cost:", sum(r["cost"] for r in three_call_results) / len(three_call_results))
```

### Step 3: Analyze in LangSmith

1. **Go to LangSmith Dashboard**
2. **Filter by Project**: Compare `capacity-chatbot-react` vs `capacity-chatbot-3calls`
3. **Create Comparison View**:
   - Select multiple runs
   - Click "Compare"
   - See side-by-side comparison

4. **Key Comparisons**:
   - **Cost**: Total cost per query
   - **Latency**: Time to first token + total time
   - **Token Usage**: Input vs output tokens
   - **Tool Calls**: Number and correctness

---

## 4. Prompt Template Testing

### A. Create Multiple Prompt Variants

In `prompts.py`, create variants:

```python
def get_capacity_agent_system_prompt_v1(knowledge_base, cached_data_info, current_time):
    """Original prompt - detailed instructions."""
    # ... your current prompt

def get_capacity_agent_system_prompt_v2(knowledge_base, cached_data_info, current_time):
    """Concise prompt - shorter, more direct."""
    return f"""You are a capacity chatbot assistant.

{knowledge_base}

{cached_data_info}

TOOLS: get_rules, get_capacity, get_first_available_slot, search_opcode
Use tools when needed. Answer from knowledge base when possible.
"""

def get_capacity_agent_system_prompt_v3(knowledge_base, cached_data_info, current_time):
    """Structured prompt - with examples."""
    return f"""You are a capacity chatbot assistant.

{knowledge_base}

{cached_data_info}

EXAMPLES:
- "What's capacity?" → Use get_capacity
- "What are rules?" → Use get_rules
- "What is capacity?" → Answer from knowledge base

TOOLS: get_rules, get_capacity, get_first_available_slot, search_opcode
"""
```

### B. Test Each Variant

In `capacity_agent.py`:

```python
# Add prompt version to metadata
prompt_version = os.getenv("PROMPT_VERSION", "v1")

if prompt_version == "v1":
    system_prompt = get_capacity_agent_system_prompt_v1(...)
elif prompt_version == "v2":
    system_prompt = get_capacity_agent_system_prompt_v2(...)
elif prompt_version == "v3":
    system_prompt = get_capacity_agent_system_prompt_v3(...)

# Add to metadata
agent_config = {
    **agent_config,
    "metadata": {
        **agent_config.get("metadata", {}),
        "prompt_version": prompt_version
    }
}
```

### C. Compare Results

1. Run same test queries with each prompt version
2. Tag runs: `["prompt-v1"]`, `["prompt-v2"]`, `["prompt-v3"]`
3. Compare in LangSmith:
   - Which version has lowest cost?
   - Which version has best accuracy?
   - Which version is fastest?

---

## 5. Model Comparison

### A. Test Different Models

Update `.env`:

```bash
# Test GPT-4o Mini (current)
MODEL=gpt-4o-mini
LANGCHAIN_PROJECT=capacity-chatbot-gpt4o-mini

# Test GPT-4o (more capable, more expensive)
MODEL=gpt-4o
LANGCHAIN_PROJECT=capacity-chatbot-gpt4o

# Test GPT-3.5 Turbo (cheapest, less capable)
MODEL=gpt-3.5-turbo
LANGCHAIN_PROJECT=capacity-chatbot-gpt35
```

### B. Compare Metrics

For each model, track:
- **Cost per Query**: Model pricing varies significantly
- **Latency**: Some models are faster
- **Accuracy**: Quality of responses
- **Token Usage**: Some models are more verbose

**Example Comparison**:
```
GPT-4o Mini:
- Cost: $0.002/query
- Latency: 2.1s
- Accuracy: 85%
- Tokens: 1,800

GPT-4o:
- Cost: $0.015/query (7.5x more expensive!)
- Latency: 3.5s
- Accuracy: 95%
- Tokens: 2,200

GPT-3.5 Turbo:
- Cost: $0.001/query (cheapest)
- Latency: 1.8s
- Accuracy: 75%
- Tokens: 1,500

Recommendation: GPT-4o Mini is best balance! ✅
```

---

## 6. Scoring & Evaluation

### A. Manual Scoring

**Create a Dataset in LangSmith**:

1. Go to LangSmith → Datasets
2. Click "Create Dataset"
3. Name it: "Capacity Chatbot Test Set"
4. Add test queries with expected outputs

**Example Dataset**:
```json
{
  "inputs": {
    "query": "get me tomorrow capacity"
  },
  "outputs": {
    "expected_tool": "get_capacity",
    "expected_params": {
      "dates": ["2025-01-06"]
    },
    "expected_response_contains": ["capacity", "tomorrow", "appointments"]
  }
}
```

### B. Automated Scoring

**Create Evaluators**:

```python
# scripts/evaluators.py
from langsmith import evaluate
from langsmith.schemas import Example, Run

def tool_call_correctness(run: Run, example: Example) -> dict:
    """Check if correct tool was called."""
    tool_calls = run.outputs.get("tool_calls", [])
    expected_tool = example.outputs.get("expected_tool")
    
    if not expected_tool:
        return {"score": 1.0}  # No tool expected
    
    called_tools = [tc.get("name") for tc in tool_calls]
    is_correct = expected_tool in called_tools
    
    return {
        "score": 1.0 if is_correct else 0.0,
        "expected": expected_tool,
        "actual": called_tools
    }

def response_relevance(run: Run, example: Example) -> dict:
    """Check if response contains expected keywords."""
    response = run.outputs.get("response_message", "").lower()
    expected_keywords = example.outputs.get("expected_response_contains", [])
    
    matches = sum(1 for keyword in expected_keywords if keyword.lower() in response)
    score = matches / len(expected_keywords) if expected_keywords else 1.0
    
    return {
        "score": score,
        "matches": matches,
        "total": len(expected_keywords)
    }

# Run evaluation
results = evaluate(
    lambda inputs: graph.ainvoke(inputs),
    data="capacity-chatbot-test-set",
    evaluators=[tool_call_correctness, response_relevance],
    experiment_prefix="capacity-chatbot-eval"
)
```

### C. Toxic Content Detection

LangSmith has built-in toxic content detection:

1. Go to LangSmith → Settings
2. Enable "Content Safety"
3. Set up filters for:
   - Toxic language
   - PII (Personal Identifiable Information)
   - Sensitive data

**In Code**:
```python
from langsmith import Client

client = Client()

# Check for toxic content
result = client.check_content_safety(
    text=response_message,
    checks=["toxicity", "pii", "sensitive_data"]
)

if result["toxicity"]["flagged"]:
    logger.warning(f"Toxic content detected: {result['toxicity']['score']}")
```

---

## 7. Best Practices

### A. Organize Your Experiments

**Project Naming Convention**:
```
capacity-chatbot-{approach}-{model}-{version}
Examples:
- capacity-chatbot-react-gpt4o-mini-v1
- capacity-chatbot-3calls-gpt4o-mini-v1
- capacity-chatbot-react-gpt4o-v2
```

**Tag Strategy**:
```python
tags = [
    "approach:react",  # or "approach:3calls"
    "model:gpt-4o-mini",
    "version:v1.0",
    "environment:production",
    "feature:capacity-queries"
]
```

### B. Track Key Metrics Over Time

**Create a Dashboard**:
1. Go to LangSmith → Dashboards
2. Create new dashboard: "Capacity Chatbot Metrics"
3. Add widgets for:
   - Cost per query (line chart)
   - Latency P95 (line chart)
   - Error rate (bar chart)
   - Tool call accuracy (gauge)

### C. Set Up Alerts

**Cost Alerts**:
```python
# If cost exceeds threshold
if daily_cost > 100:  # $100/day
    send_alert("Cost threshold exceeded!")
```

**Error Rate Alerts**:
```python
# If error rate > 5%
if error_rate > 0.05:
    send_alert("Error rate too high!")
```

### D. A/B Testing Framework

**Create a Simple A/B Test**:

```python
import random

def get_approach_for_user(user_id: str) -> str:
    """Assign user to A or B group."""
    # Use consistent hashing for same user = same group
    hash_value = hash(user_id) % 100
    return "react" if hash_value < 50 else "3calls"

# In your agent
approach = get_approach_for_user(user_id)
if approach == "react":
    # Use ReAct agent
else:
    # Use 3 LLM calls approach

# Track in metadata
metadata = {
    "ab_test_group": approach,
    "user_id": user_id
}
```

### E. Continuous Monitoring

**Weekly Review Checklist**:
- [ ] Review cost trends (is it increasing?)
- [ ] Check latency P95 (is it degrading?)
- [ ] Review error logs (new failure patterns?)
- [ ] Compare model performance (should we switch?)
- [ ] Analyze user feedback (thumbs up/down ratio)

---

## 8. Practical Example: Comparing ReAct vs 3 LLM Calls

### Step-by-Step Process:

1. **Create Test Dataset** (10-20 representative queries)
2. **Run ReAct Approach**:
   ```bash
   LANGCHAIN_PROJECT=capacity-chatbot-react langgraph dev
   ```
   - Run all test queries
   - Note project name in LangSmith

3. **Run 3 LLM Calls Approach** (if you still have it):
   ```bash
   LANGCHAIN_PROJECT=capacity-chatbot-3calls langgraph dev
   ```
   - Run same test queries
   - Note project name in LangSmith

4. **Compare in LangSmith**:
   - Go to LangSmith Dashboard
   - Filter by project
   - Compare metrics:
     - **Cost**: ReAct should be ~66% cheaper
     - **Latency**: ReAct should be ~60% faster
     - **Accuracy**: Should be similar (if not better)

5. **Make Decision**:
   - If ReAct wins on all metrics → Switch to ReAct ✅
   - If 3 LLM calls has better accuracy → Investigate why
   - If cost/latency similar → Choose simpler approach (ReAct)

---

## 9. Success Parameters (What to Optimize For)

### Priority Order:

1. **Cost** (Highest Priority)
   - Target: < $0.003 per query
   - Current (3 LLM calls): ~$0.006 per query
   - Target (ReAct): ~$0.002 per query
   - **Success**: 66% cost reduction ✅

2. **Latency** (High Priority)
   - Target: P95 < 5 seconds
   - Current (3 LLM calls): ~12s
   - Target (ReAct): ~4.5s
   - **Success**: 62% latency reduction ✅

3. **Accuracy** (High Priority)
   - Target: > 90% correct tool calls
   - Current: ~85%
   - Target: Maintain or improve
   - **Success**: No degradation ✅

4. **User Satisfaction** (Medium Priority)
   - Target: > 80% thumbs up
   - Measure via: User feedback in UI
   - **Success**: Positive feedback ✅

---

## 10. Quick Reference: LangSmith Features

| Feature | Use Case | How to Access |
|---------|----------|---------------|
| **Traces** | View individual runs | Dashboard → Traces |
| **Projects** | Organize experiments | Dashboard → Projects |
| **Datasets** | Test sets | Dashboard → Datasets |
| **Evaluations** | Automated scoring | Dashboard → Evaluations |
| **Dashboards** | Visualize metrics | Dashboard → Dashboards |
| **Alerts** | Cost/error monitoring | Settings → Alerts |
| **Content Safety** | Toxic content detection | Settings → Content Safety |
| **Compare** | Side-by-side comparison | Select runs → Compare |

---

## 11. Next Steps

1. **Set up your first experiment**: Compare ReAct vs 3 LLM calls
2. **Create a test dataset**: 20-30 representative queries
3. **Run both approaches**: Tag appropriately
4. **Analyze results**: Focus on cost, latency, accuracy
5. **Make decision**: Based on data, not intuition
6. **Iterate**: Continue optimizing based on results

---

## Questions to Answer with LangSmith:

1. **Is ReAct better than 3 LLM calls?**
   - Compare cost, latency, accuracy
   - Answer: Yes, if cost/latency better AND accuracy maintained

2. **Which model is best?**
   - Test GPT-4o, GPT-4o Mini, GPT-3.5 Turbo
   - Answer: GPT-4o Mini (best balance)

3. **Which prompt works best?**
   - Test different prompt variants
   - Answer: The one with best accuracy + lowest cost

4. **What's our error rate?**
   - Monitor over time
   - Answer: Should be < 5%

5. **Are we improving?**
   - Track metrics over time
   - Answer: Yes, if cost/latency decreasing, accuracy stable/increasing

---

**Remember**: Data-driven decisions > Intuition. Use LangSmith to make informed choices! 🚀

