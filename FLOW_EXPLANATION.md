# Complete Flow Explanation: "fetch me capacity for loaner"

This document explains **exactly** what happens when you type "fetch me capacity for loaner" from start to finish.

---

## 🎯 **HIGH-LEVEL OVERVIEW**

```
Your Message → LangGraph API → Graph → capacity_agent → ReAct Agent → LLM Decision → 
get_capacity_tool → UUID Mapping → API Request → kappointment-api → Response → 
Formatting → LLM Response → Your UI
```

---

## 📋 **STEP-BY-STEP DETAILED FLOW**

### **STEP 1: Your Message Arrives** 
**Location:** UI → LangGraph API

**What happens:**
- You type: `"fetch me capacity for loaner"`
- UI sends POST request to: `http://localhost:8123/threads/{threadId}/runs/wait`
- Request body includes:
  ```json
  {
    "input": {
      "messages": [{"role": "human", "content": "fetch me capacity for loaner"}],
      "dealer_uuid": "...",
      "department_uuid": "...",
      "mkid": "...",
      "cached_data": {...}
    }
  }
  ```

---

### **STEP 2: LangGraph Processes Request**
**Location:** `langgraph dev` server

**What happens:**
- LangGraph receives the request
- Creates/retrieves thread state from SQLite checkpointer
- Converts input to `CapacityChatbotState`
- Routes to the graph defined in `graph.py`

---

### **STEP 3: Graph Routes to capacity_agent**
**Location:** `src/capacity_chatbot/graph.py`

**Code:**
```python
# Line 24-33
builder = StateGraph(CapacityChatbotState, input_schema=InputState)
builder.add_node("capacity_agent", capacity_agent)
builder.add_edge("__start__", "capacity_agent")
builder.add_edge("capacity_agent", END)
```

**What happens:**
- Graph sees `__start__` → routes to `capacity_agent` node
- Calls `capacity_agent(state, config)`

---

### **STEP 4: capacity_agent Initializes**
**Location:** `src/capacity_chatbot/nodes/capacity_agent.py` (Line 139-259)

**What happens:**

#### 4.1 Load Test Data (if needed)
```python
# Line 162
ensure_cached_data(state)  # Loads transport options, advisors, teams
```

#### 4.2 Get Department UUID
```python
# Line 165-178
department_uuid = state.department_uuid or os.getenv("DEFAULT_DEPARTMENT_UUID")
```

#### 4.3 Build System Prompt
```python
# Line 195-212
knowledge_base = get_knowledge_base_section(condensed=True)  # ~200 tokens
cached_data_info = _format_cached_data(state)  # "Loaner, Shuttle, Rental..."
system_prompt = get_capacity_agent_system_prompt(
    knowledge_base=knowledge_base,
    cached_data_info=cached_data_info,
    current_time="Monday, January 5, 2026 11:53 AM"
)
```

**System prompt includes:**
- Knowledge base (Q&A, documentation)
- Available transport options: "Loaner, Shuttle, Rental..."
- Available advisors: "Art, Vishal, Donald..."
- Available teams: "Main Shop, Express Shop..."
- Tool descriptions
- Instructions on how to use tools

#### 4.4 Create ReAct Agent
```python
# Line 214-219
agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini"),
    tools=[get_rules_tool, get_capacity_tool, get_first_available_slot_tool, search_opcode_tool],
    prompt=system_prompt
)
```

#### 4.5 Pass State to Tools
```python
# Line 225
agent_config = _create_agent_config(state, config)
# This puts state in: config["configurable"]["state"]
```

#### 4.6 Invoke ReAct Agent
```python
# Line 228
result = await agent.ainvoke(agent_input, config=agent_config)
```

**What ReAct does:**
- LLM reads your message: "fetch me capacity for loaner"
- LLM sees available tools and decides: "I need to call `get_capacity_tool`"
- LLM extracts parameters:
  - `transport_option_names=["loaner"]` (from your message)
  - `dates=None` (defaults to tomorrow)
- LLM calls: `get_capacity_tool(transport_option_names=["loaner"])`

---

### **STEP 5: get_capacity_tool Executes**
**Location:** `src/capacity_chatbot/tools/capacity_tools.py` (Line 100-295)

**What happens:**

#### 5.1 Get State from Config
```python
# Line 144
state: CapacityChatbotState = config.get("configurable", {}).get("state")
```

#### 5.2 Extract Required Data
```python
# Line 150-155
department_uuid = state.department_uuid
mkid = state.mkid or os.getenv("MYKAARMA_MKID")
cached_data = state.cached_data or {}
```

#### 5.3 Load Test Data (if empty)
```python
# Line 162-167
if not cached_data:
    ensure_cached_data(state)  # Loads test data
    cached_data = state.cached_data
```

#### 5.4 Create UUID Mapper
```python
# Line 179-180
uuid_mapper = UUIDMapper(cached_data)
# Builds maps:
#   transport_map = {"-f_LNZEWiHQg4AbTH...": "Loaner", ...}
#   advisor_map = {"65fbbd1b95e323d5...": "Art", ...}
```

#### 5.5 Map "loaner" → UUID
```python
# Line 193-197
for name in transport_option_names:  # ["loaner"]
    uuid = uuid_mapper.get_transport_uuid_by_name(name)  # "loaner" → "-f_LNZEWiHQg4AbTH..."
    if uuid:
        final_transport_option_uuids.append(uuid)
```

**UUIDMapper logic:**
```python
# src/capacity_chatbot/utils/uuid_mapper.py (Line 102-105)
name_lower = "loaner".lower()  # "loaner"
for uuid, transport_name in transport_map.items():  # {"-f_LNZEWiHQg4AbTH...": "Loaner"}
    if "loaner" in "loaner".lower():  # True!
        return uuid  # "-f_LNZEWiHQg4AbTH-b_qmDTO8CKwkSQXCtpYFHfWGw"
```

#### 5.6 Handle Dates
```python
# Line 227-246
if not dates:
    tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%d")  # "2026-01-07"
    dates = [tomorrow]
```

#### 5.7 Build entityMap
```python
# Line 248-254
entity_map = {}
field_combinations = []

if final_transport_option_uuids:  # ["-f_LNZEWiHQg4AbTH..."]
    entity_map["TRANSPORT_OPTION_UUID"] = final_transport_option_uuids
    field_combinations.append(["TRANSPORT_OPTION_UUID"])
```

**Result:**
```python
entity_map = {
    "TRANSPORT_OPTION_UUID": ["-f_LNZEWiHQg4AbTH-b_qmDTO8CKwkSQXCtpYFHfWGw"]
}
field_combinations = [["TRANSPORT_OPTION_UUID"]]
```

#### 5.8 Call get_capacity_tool_impl
```python
# Line 277-290
result = await get_capacity_tool_impl(
    department_uuid=department_uuid,
    applicability_rule_field=ApplicabilityRuleField.DATE,
    applicability_field_values=["2026-01-07"],
    capacity_type_set=[CapacityType.APPOINTMENT_COUNT],
    entity_map=entity_map,  # {"TRANSPORT_OPTION_UUID": ["-f_LNZEWiHQg4AbTH..."]}
    field_combinations=[["TRANSPORT_OPTION_UUID"]],
    rule_matching_criteria=RuleMatchingCriteria.INCLUSIVELY_MATCHES,
    mkid=mkid,
    cached_data=cached_data,
)
```

---

### **STEP 6: get_capacity_tool_impl Builds Request**
**Location:** `src/capacity_chatbot/tools.py` (Line 681-820)

**What happens:**

#### 6.1 Build Request Payload
```python
# Line 741-787
request_payload = {
    "applicabilityRuleField": "DATE",
    "applicabilityFieldValues": ["2026-01-07"],
    "capacityTypeSet": ["APPOINTMENT_COUNT"],
    "entityMap": {
        "TRANSPORT_OPTION_UUID": ["-f_LNZEWiHQg4AbTH-b_qmDTO8CKwkSQXCtpYFHfWGw"]
    },
    "fieldCombinations": [["TRANSPORT_OPTION_UUID"]],
    "ruleMatchingCriteria": "INCLUSIVELY_MATCHES",
    "includeDiagnostics": True  # ← KEY: This requests diagnostics
}
```

#### 6.2 Log Request (YOU SEE THIS IN TERMINAL)
```python
# Line 789-797
logger.info("=" * 80)
logger.info("get_capacity API Request Details:")
logger.info(f"  URL: POST /appointment/v2/webservice/department/{department_uuid}/capacity")
logger.info("  Request Body (JSON):")
logger.info(json.dumps(request_payload, indent=2, default=str))
logger.info("=" * 80)
```

**Terminal output:**
```
================================================================================
get_capacity API Request Details:
  URL: POST /appointment/v2/webservice/department/8ec821aefe98664ab15df7c426c3c46f9c37d0b1aeda9ff58df3db89bb0a55a3/capacity
  Department UUID: 8ec821aefe98664ab15df7c426c3c46f9c37d0b1aeda9ff58df3db89bb0a55a3
  Request Body (JSON):
  {
    "applicabilityRuleField": "DATE",
    "applicabilityFieldValues": ["2026-01-07"],
    "capacityTypeSet": ["APPOINTMENT_COUNT"],
    "entityMap": {
      "TRANSPORT_OPTION_UUID": ["-f_LNZEWiHQg4AbTH-b_qmDTO8CKwkSQXCtpYFHfWGw"]
    },
    "fieldCombinations": [["TRANSPORT_OPTION_UUID"]],
    "ruleMatchingCriteria": "INCLUSIVELY_MATCHES",
    "includeDiagnostics": true
  }
================================================================================
```

#### 6.3 Initialize API Client
```python
# Line 800-801
config = KAppointmentAPIConfig(mkid=mkid)
client = KAppointmentAPIClient(config=config)
```

---

### **STEP 7: HTTP Request to kappointment-api**
**Location:** `src/capacity_chatbot/services/kappointment_client.py` (Line 36-66)

**What happens:**

#### 7.1 Build URL
```python
# Line 50
url = f"{base_url}/appointment/v2/webservice/department/{department_uuid}/capacity"
# "https://srishti244.mykaarma.dev/appointment/v2/webservice/department/8ec821.../capacity"
```

#### 7.2 Log HTTP Request (YOU SEE THIS IN TERMINAL)
```python
# Line 55-64
logger.info("=" * 80)
logger.info("HTTP Request to kappointment-api:")
logger.info(f"  Method: POST")
logger.info(f"  URL: {url}")
logger.info(f"  Cookies: mkid={cookies.get('mkid', 'NOT_SET')[:20]}...")
logger.info("  Request Body:")
logger.info(json.dumps(request, indent=2, default=str))
logger.info("=" * 80)
```

#### 7.3 Make HTTP POST Request
```python
# Line 65
response = await self._client.post(url, json=request_payload, cookies=cookies)
```

**HTTP Request:**
```
POST https://srishti244.mykaarma.dev/appointment/v2/webservice/department/8ec821.../capacity
Cookie: mkid=602d4551-2a31-471c-9b4d-91fd7da632f6
Content-Type: application/json

{
  "applicabilityRuleField": "DATE",
  "applicabilityFieldValues": ["2026-01-07"],
  "capacityTypeSet": ["APPOINTMENT_COUNT"],
  "entityMap": {
    "TRANSPORT_OPTION_UUID": ["-f_LNZEWiHQg4AbTH-b_qmDTO8CKwkSQXCtpYFHfWGw"]
  },
  "fieldCombinations": [["TRANSPORT_OPTION_UUID"]],
  "ruleMatchingCriteria": "INCLUSIVELY_MATCHES",
  "includeDiagnostics": true
}
```

#### 7.4 Parse Response
```python
# Line 66
return response.json()
```

---

### **STEP 8: API Response Received**
**Location:** `src/capacity_chatbot/tools.py` (Line 805-820)

**Response structure:**
```json
{
  "capacityMap": {
    "APPOINTMENT_COUNT": {
      "2026-01-07": {
        "combinationWiseCapacity": {
          "TRANSPORT_OPTION_UUID=-f_LNZEWiHQg4AbTH...": {
            "usedCount": 0.0,
            "totalCount": 5.0,
            "diagnostics": {
              "limitBreakdown": {
                "dealerScheduleLimit": 20.0,
                "individualScheduleLimit": null,
                "operationLimit": null,
                "ruleLimit": 5.0,
                "transportOptionLimit": 5.0,
                "effectiveLimit": 5.0,
                "limitSource": "TRANSPORT_OPTION",
                "limitSourceDetails": "Transport option 'Loaner' has a limit of 5 appointments"
              },
              "bottleneckReason": "Transport option limit is constraining capacity"
            }
          }
        }
      }
    }
  }
}
```

---

### **STEP 9: Format Response for LLM**
**Location:** `src/capacity_chatbot/tools.py` (Line 258-420)

**What happens:**

#### 9.1 Format Capacity Data
```python
# Line 813
formatted_result = _format_capacity_response(result, uuid_mapper)
```

**Formatting logic:**
```python
# Line 300-341
for combination_key, capacity_data in combination_wise_capacity.items():
    used_count = capacity_data.get("usedCount", 0.0)  # 0.0
    total_count = capacity_data.get("totalCount", 5.0)  # 5.0
    diagnostics = capacity_data.get("diagnostics")  # {...}
    
    # Replace UUID with name
    display_key = "Transport: Loaner"  # (from UUIDMapper)
    
    formatted_parts.append(f"  Combination: Transport: Loaner")
    formatted_parts.append(f"  - Used: 0 appointments")
    formatted_parts.append(f"  - Total: 5 appointments")
    formatted_parts.append(f"  - Available: 5 appointments")
```

#### 9.2 Format Diagnostics (IF AVAILABLE)
```python
# Line 344-420
if diagnostics:
    limit_breakdown = diagnostics.get("limitBreakdown", {})
    bottleneck_reason = diagnostics.get("bottleneckReason", "")
    
    formatted_parts.append("  DIAGNOSTICS:")
    formatted_parts.append("  Contributing Limits:")
    formatted_parts.append(f"    - Dealer Schedule: 20.0 appointments")
    formatted_parts.append(f"    - Transport Option Limit: 5.0 appointments")
    formatted_parts.append(f"    - Capacity Rule: 5.0 appointments")
    formatted_parts.append(f"  Bottleneck: Transport option limit is constraining capacity")
    formatted_parts.append("  Actionable Advice:")
    formatted_parts.append("    - Increase transport option limit for 'Loaner'")
    formatted_parts.append("    - Modify capacity rules affecting this transport option")
```

**Formatted output:**
```
=== APPOINTMENT_COUNT CAPACITY ===

Date/Day: 2026-01-07

  Combination: Transport: Loaner
  - Used: 0 appointments
  - Total: 5 appointments
  - Available: 5 appointments

  DIAGNOSTICS:
  Contributing Limits:
    - Dealer Schedule: 20.0 appointments
    - Transport Option Limit: 5.0 appointments
    - Capacity Rule: 5.0 appointments
  Bottleneck: Transport option limit is constraining capacity
  Actionable Advice:
    - Increase transport option limit for 'Loaner'
    - Modify capacity rules affecting this transport option
```

#### 9.3 Return Formatted Result
```python
# Line 816-820
return {
    "formatted_summary": formatted_result,  # String for LLM
    "raw_data": result,  # Full JSON for debugging
    "has_data": True
}
```

---

### **STEP 10: Tool Returns to ReAct Agent**
**Location:** `src/capacity_chatbot/tools/capacity_tools.py` (Line 290-295)

**What happens:**
```python
# Line 290-295
if isinstance(result, dict) and "formatted_summary" in result:
    return result["formatted_summary"]  # Returns formatted string to LLM
```

**LLM receives:**
```
=== APPOINTMENT_COUNT CAPACITY ===

Date/Day: 2026-01-07

  Combination: Transport: Loaner
  - Used: 0 appointments
  - Total: 5 appointments
  - Available: 5 appointments

  DIAGNOSTICS:
  Contributing Limits:
    - Dealer Schedule: 20.0 appointments
    - Transport Option Limit: 5.0 appointments
    - Capacity Rule: 5.0 appointments
  Bottleneck: Transport option limit is constraining capacity
  Actionable Advice:
    - Increase transport option limit for 'Loaner'
    - Modify capacity rules affecting this transport option
```

---

### **STEP 11: LLM Generates Final Response**
**Location:** ReAct agent (internal)

**What happens:**
- LLM receives tool result
- LLM reads the formatted capacity data
- LLM generates user-friendly response:

```
For tomorrow (2026-01-07), the capacity for Loaner transport is:
- Total: 5 appointments
- Available: 5 appointments
- Used: 0 appointments

The capacity is currently limited by the transport option limit of 5 appointments. 
The dealer schedule allows 20 appointments, but the Loaner transport option 
has a limit of 5 appointments.
```

---

### **STEP 12: Response Returns to UI**
**Location:** `capacity_agent` → LangGraph → UI

**What happens:**
```python
# Line 231-238
final_message = result["messages"][-1].content
response = {
    "assistant_message": final_message,
    "messages": [AIMessage(content=final_message)],
}
return response
```

**UI receives:**
```json
{
  "assistant_message": "For tomorrow (2026-01-07), the capacity for Loaner transport is: ...",
  "messages": [...]
}
```

---

## 🔍 **HOW TO SEE REQUEST BODY & RESPONSE**

### **Method 1: VS Code Terminal (Current)**
✅ **You're already seeing this!**

When you run `langgraph dev`, logs appear in your terminal:
```
================================================================================
get_capacity API Request Details:
  URL: POST /appointment/v2/webservice/department/.../capacity
  Request Body (JSON):
  {
    "entityMap": {...},
    "includeDiagnostics": true
  }
================================================================================
```

### **Method 2: LangSmith Trace**
1. Open LangSmith UI
2. Go to "Tracing" → Find your trace
3. Expand `get_capacity_tool` step
4. Look for:
   - **Input:** `{'transport_option_names': ['Loaner'], 'dates': ['2026-01-07']}`
   - **Output:** Formatted capacity summary
   - **Logs:** Request body (if captured)

### **Method 3: Docker Logs**
```bash
docker logs -f capacity-chatbot-service | grep -A 50 "get_capacity API Request"
```

### **Method 4: Add Response Logging**
I can add logging to show the **raw API response** too. Would you like me to add that?

---

## 🐛 **WHY DIAGNOSTICS MIGHT BE MISSING**

If diagnostics are not showing in the formatted output, check:

1. **Is `includeDiagnostics: true` in request?** ✅ (We always set this)
2. **Does API response include `diagnostics`?** Check raw response
3. **Is diagnostics formatting code working?** Check `_format_capacity_response` (Line 344-420)

**To debug:**
- Check terminal logs for raw API response
- Verify `diagnostics` field exists in response
- Check if formatting code is executing (add more logs)

---

## 📝 **SUMMARY**

**Request Flow:**
1. Your message → LangGraph → `capacity_agent`
2. ReAct agent → LLM decides → `get_capacity_tool(transport_option_names=["loaner"])`
3. Tool maps "loaner" → UUID using `UUIDMapper`
4. Tool builds `entityMap = {"TRANSPORT_OPTION_UUID": ["-f_LNZEWiHQg4AbTH..."]}`
5. Tool calls `get_capacity_tool_impl` with `entityMap`
6. `get_capacity_tool_impl` builds request payload with `includeDiagnostics: true`
7. HTTP POST to kappointment-api with full request body
8. API returns response with `capacityMap` and `diagnostics`
9. `_format_capacity_response` formats both capacity and diagnostics
10. Formatted string returned to LLM
11. LLM generates final user-friendly response

**Key Files:**
- `graph.py` - Graph definition
- `capacity_agent.py` - ReAct agent orchestration
- `capacity_tools.py` - Tool wrapper (UUID mapping)
- `tools.py` - Tool implementation (API call, formatting)
- `kappointment_client.py` - HTTP client
- `uuid_mapper.py` - Name ↔ UUID conversion

