"""Knowledge base for capacity chatbot - stores common questions and documentation."""

from typing import Dict, List

# Common questions users can ask (knowledge-based, no API calls needed)
# Last updated: 2026-01-06 from MyKaarma support documentation
COMMON_QUESTIONS: List[Dict[str, str]] = [
    # ========== CORE CONCEPTS ==========
    {
        "question": "What is capacity?",
        "answer": "Capacity refers to the maximum number of appointments that can be scheduled for a given time period, advisor, team, or transport option. It's controlled by multiple factors: dealer schedule limits, individual advisor limits, capacity rules, and transport option limits. The system calculates the effective capacity by taking the minimum of all these limits - the lowest one becomes the 'limiting factor' that constrains booking.",
        "category": "concept",
        "keywords": ["capacity", "what is", "definition", "limit", "limiting factor", "maximum", "appointments per day", "appt per slot", "settings"]
    },
    {
        "question": "What is a transport option?",
        "answer": "Transport options are ways customers can get to/from the service department. Common options include: Loaner (loaner vehicle), Shuttle (shuttle service), Rental (rental car), Will Wait (customer waits), Pickup and Delivery, None (customer drives themselves). Each transport option can have its own daily capacity limits and time-block restrictions.",
        "category": "concept",
        "keywords": ["transport", "option", "loaner", "shuttle", "rental", "will wait", "pickup", "delivery", "waiter", "rideshare", "uber"]
    },
    {
        "question": "What is a team?",
        "answer": "A team is a group of service advisors who work together. Teams can have their own capacity rules and assignment rules. Examples: Main Shop, Express Shop, Rotation Shop. Each team can have multiple advisors assigned to it, and rules can target specific teams.",
        "category": "concept",
        "keywords": ["team", "teams", "advisor group", "main shop", "express shop", "rotation shop", "mainshop", "express", "rotate"]
    },
    {
        "question": "What is an opcode or operation?",
        "answer": "An opcode (operation code) represents a specific service type like 'Oil Change', 'Tire Rotation', or 'Brake Inspection'. Each opcode can have its own capacity limits and be used in capacity rules and assignment rules. Opcodes can be grouped by 'Skill' categories (e.g., Oil Change Bucket: Cars, Oil Change Bucket: Trucks).",
        "category": "concept",
        "keywords": ["opcode", "operation", "service", "oil change", "tire rotation", "brake", "skill"]
    },
    {
        "question": "What does limiting factor mean in limit info?",
        "answer": "The limiting factor is the limit that's constraining capacity. The system calculates multiple limits: dealer schedule limit, individual schedule limit, capacity rule limit, transport option limit, and opcode daily limit. The LOWEST of these becomes the effective limit (limiting factor). Limit info shows which limit is the limiting factor and its source, helping you know exactly what to change to increase capacity.",
        "category": "limit-info",
        "keywords": ["limiting factor", "limiting", "constraining", "limit info", "effective limit", "source"]
    },
    {
        "question": "Why is capacity showing 0?",
        "answer": "Capacity of 0 means one of these is blocking appointments: 1) A capacity rule explicitly blocks that day/advisor/transport (ruleLimit = 0), 2) Individual advisor schedule has 0 appointments for that day, 3) Transport option is disabled or has 0 limit, 4) Dealer schedule has 0 for that day. Check the 'limitingFactor' field in the limit info to see the exact cause and limiting source.",
        "category": "troubleshooting",
        "keywords": ["zero", "0", "none", "no capacity", "blocked", "why", "can't book", "unavailable", "showing zero", "no available", "not allow", "error message", "no appointments"]
    },

    # ========== CAPACITY RULES ==========
    {
        "question": "How do capacity rules work?",
        "answer": "Capacity rules restrict appointment counts using IF-THEN logic. Structure: 1) IF conditions (Date/Time, Team, Advisor, Transport Option, Opcode, Vehicle details), 2) THEN restriction (Total Appointments <= X, Total Service Hours <= X), 3) PER interval (Day, Hour, Multi-Slot, Advisor). Example: 'IF Transport Option = Loaner AND Team = Main Shop THEN Total Appointments <= 30 PER Day'. Multiple conditions can be joined with AND - all must be true for the rule to apply.",
        "category": "rules",
        "keywords": ["rules", "how do", "work", "capacity rules", "if", "then", "per"]
    },
    {
        "question": "How do I create a capacity rule?",
        "answer": "To create a capacity rule: 1) Go to Settings > Capacity Rules, 2) Click '+ Add Rule', 3) Define IF conditions - choose category (Date, Team, Transport Option, Opcode, etc.), operator (in, not in, on, between), and values, 4) Use AND to add multiple conditions, 5) Define THEN clause - what to restrict (Total Appointments, Service Hours) and the limit (e.g., <= 30), 6) Set PER interval (Day, Hour, Advisor), 7) Click Continue, verify summary, then Save Rule to activate.",
        "category": "how-to",
        "keywords": ["create", "add", "new", "capacity rule", "how to", "setup", "set up", "block", "restrict", "limit by"]
    },
    {
        "question": "How do I increase capacity limited by a capacity rule?",
        "answer": "To increase capacity limited by a capacity rule: 1) Go to Settings > Capacity Rules, 2) Find the rule (name shown in limitInfo details field), 3) Click Edit, 4) In the THEN clause, increase the limit value (e.g., change <= 30 to <= 50), 5) Save the rule. The change takes effect immediately for new capacity calculations.",
        "category": "how-to",
        "keywords": ["increase", "capacity", "rule", "limit", "how to", "change", "modify", "capacity rule", "then clause"]
    },
    {
        "question": "What are the IF categories in capacity rules?",
        "answer": "IF categories define when a capacity rule applies: Date/Date and Time/Day (calendar triggers), Time/Hour/Multi-Slot (time-based), Department/Team/Advisor (organizational), Transport Option (Loaner, Shuttle, etc.), Source/Priority/Customer Type (booking origin), Vehicle Model/Year/VIN (vehicle criteria), OP Code/Service Group/Skill (service type). Use AND to combine multiple conditions.",
        "category": "rules",
        "keywords": ["if", "categories", "conditions", "capacity rule", "date", "time", "team", "transport", "vehicle model", "vehicle year", "prior to", "older than"]
    },
    {
        "question": "What are the THEN options in capacity rules?",
        "answer": "THEN options define what gets restricted: Total Appointment (limits count of appointments), Total Service Hours (limits cumulative service duration), Total Wait (limits waiting customers), Total Loaner (limits loaner vehicles). Combined with PER interval: Day (daily limit), Hour (hourly limit), Multi-Slot (across time slots), Advisor (per individual advisor).",
        "category": "rules",
        "keywords": ["then", "options", "capacity rule", "appointment", "service hours", "per", "day", "hour"]
    },
    {
        "question": "What operators can I use in capacity rules?",
        "answer": "Capacity rule operators: 'on' (matches specific day), 'in between' (range between two dates), 'on or after' (starting date and forward), 'in' (contains value), 'not in' (excludes value), 'in any' (matches any of selected values), '<=' (less than or equal - used for setting limits). These operators let you precisely define when rules apply.",
        "category": "rules",
        "keywords": ["operators", "on", "in", "between", "not in", "less than", "capacity rule"]
    },

    # ========== ASSIGNMENT RULES ==========
    {
        "question": "What is an assignment rule?",
        "answer": "Assignment rules control which advisors, teams, or transport options are AVAILABLE for an appointment based on criteria. Unlike capacity rules (which limit counts), assignment rules FILTER options. Built with IF/THEN logic: IF conditions are met, THEN only specific options are allowed. Example: 'IF Opcode Duration <= 30, THEN Teams in Express Shop' - quick services only go to Express Shop.",
        "category": "concept",
        "keywords": ["assignment", "rule", "routing", "assign", "filter", "available", "options", "restrict", "only available", "who can book", "service team only"]
    },
    {
        "question": "What's the difference between capacity rules and assignment rules?",
        "answer": "Capacity Rules limit VOLUME - how many appointments can be booked (e.g., 'max 5 oil changes per hour'). Assignment Rules control ROUTING - which options are available (e.g., 'oil changes only go to Express Team'). Think: Capacity = 'how many', Assignment = 'who/where'. A user might not be able to book because either: the capacity is full (capacity rule) OR the advisor/team isn't assigned to handle that service (assignment rule).",
        "category": "rules",
        "keywords": ["difference", "capacity", "assignment", "compare", "vs", "versus"]
    },
    {
        "question": "How do I create an assignment rule?",
        "answer": "To create an assignment rule: 1) Go to Settings > Assignment Rules, 2) Click '+ Add Rule', 3) Name your rule descriptively, 4) Define IF conditions - select category (Opcode Duration, Vehicle Make, Source, etc.), operator (<=, in, not in), and values, 5) Define THEN restriction - what's allowed (Teams, Advisors, Transport Options), 6) Use AND to add multiple conditions, 7) Ensure 'Activate Rule' toggle is ON, 8) Save.",
        "category": "how-to",
        "keywords": ["create", "add", "new", "assignment rule", "how to", "setup", "set up", "make it to where", "only available for"]
    },
    {
        "question": "What IF conditions can assignment rules use?",
        "answer": "Assignment rule IF categories: Appointment Duration, Opcodes, Opcode Duration, Recall, Skill (service details); Customer Name/Email/Phone (customer info); Vehicle Make/Year/Model (vehicle details); API/DealerApp/DMS/Mobile/Web (booking source); Service Advisor/Teams/Transport Option (current assignments). Operators include >, >=, <, <=, =, in, not in, in any.",
        "category": "rules",
        "keywords": ["assignment", "if", "conditions", "categories", "opcode", "vehicle", "source"]
    },
    {
        "question": "What is a conflicting assignment rule?",
        "answer": """A conflict happens when two or more assignment rules can match the same request (overlapping IF conditions), but they produce different outcomes (different THEN actions).

**CRITICAL: There is NO priority system for assignment rules. Conflicts mean scheduling will break entirely.**

**Example:**
- Rule 1: IF op_code in {A, B, C} → assign Team A
- Rule 2: IF op_code in {A} → assign Team B
- For op_code = A: Both rules match, but recommend different teams → CONFLICT!

**Conflict Types:**
1. **Overlap conflict** (most common): Partial overlap in IF conditions
2. **Exact duplicate**: Same IF conditions, different THEN actions
3. **Opposite action**: One rule assigns, another blocks the same entity

**Detection:**
When you fetch assignment rules using get_rules, the system will automatically detect and flag any conflicts.""",
        "category": "rules",
        "keywords": ["conflict", "conflicting", "assignment rule", "overlap", "break", "not working", "priority", "duplicate"]
    },
    {
        "question": "How do I fix conflicting assignment rules?",
        "answer": """To resolve conflicting assignment rules:

**Step 1: Identify the overlap**
- Note which rules share overlapping IF conditions
- Identify what values/inputs trigger both rules

**Step 2: Decide the correct business logic**
- Determine which rule should apply for overlapping cases
- Example: Should op_code A go to Team A or Team B?

**Step 3: Modify rules to remove overlap**

**Option A - Make conditions mutually exclusive:**
- Rule 1: IF op_code in {B, C} → Team A (remove A from list)
- Rule 2: IF op_code in {A} → Team B

**Option B - Merge into single rule:**
- Delete one rule
- Update the other to cover all needed cases

**Option C - Add differentiating conditions:**
- Use AND conditions to make rules more specific
- Example: IF op_code = A AND source = Online → Team B
- Example: IF op_code = A AND source = DealerApp → Team A

**Step 4: Verify**
Go to Settings → Assignment Rules, edit the conflicting rules, and test that scheduling works for previously conflicting scenarios.""",
        "category": "how-to",
        "keywords": ["fix", "resolve", "conflict", "conflicting", "assignment rule", "overlap", "mutually exclusive", "remove", "merge"]
    },
    # ========== TRANSPORT OPTIONS (DETAILED HOW-TO) ==========
    {
        "question": "How do I increase transport option capacity?",
        "answer": """To increase transport option capacity (e.g., Loaner, Shuttle, Pickup and Delivery):

1. Go to Settings → Appointments → Transportation Option
2. You will see two columns:
   - Left column: Transport options for Dealer App
   - Right column: Transport options for Consumer/Online Scheduler
3. Select the transport option you want to modify
4. Scroll to the capacity configuration section at the bottom
5. Increase the 'Total allowed bookings' value for that transport option
6. You can configure different capacities for:
   - Dealer App bookings
   - Online Scheduler bookings
7. For date-specific changes, click 'Allow Changes Only for Selected Dates'
8. You can also add time blocks to temporarily restrict availability during certain hours
9. Save your changes - they take effect immediately

NOTE: Transport options only set daily limits. For slot-level variability within a day, use Capacity Rules instead.""",
        "category": "how-to",
        "keywords": ["increase", "transport", "option", "capacity", "limit", "how to", "change", "modify", "loaner", "shuttle", "transportation", "loaner cars", "loaners", "waiters", "adjust"]
    },
    {
        "question": "What is the difference between Total and Online Reserve limits?",
        "answer": "For transport options: Total Limits apply to ALL appointments (dealer app + online scheduler). Online Reserve Limits are specifically reserved for online scheduler appointments only. Example: If Loaner Total = 10 and Online Reserve = 3, the dealership can book 10 total loaners, but 3 of those are guaranteed for online customers. This prevents the dealer app from using all loaners before online customers can book.",
        "category": "concept",
        "keywords": ["total", "online", "reserve", "limit", "transport", "difference"]
    },
    {
        "question": "How do I add time blocks to transport options?",
        "answer": "Time blocks restrict transport options during specific hours: 1) Go to Settings → Appointments → Transportation Option, 2) Select the transport option, 3) In the capacity configuration section, click 'Add Time Block', 4) Set the time range and limit (use 0 to block completely). Example: Block loaners from 12:00 PM - 1:00 PM lunch break by adding a time block with limit 0 for that period. This is useful for temporarily blocking transport availability during specific hours.",
        "category": "how-to",
        "keywords": ["time", "block", "hours", "transport", "restrict", "lunch", "break"]
    },
    {
        "question": "How do I enable or disable a transport option?",
        "answer": "To enable/disable transport options: 1) Go to Settings → Appointments → Transportation Option, 2) In the transport options table at the top, 3) Use the toggle switch next to each option to enable (ON) or disable (OFF). Disabled options won't appear in the online scheduler or dealer app. You can also reorder options using the hamburger icon (drag and drop) to change display order in the scheduler.",
        "category": "how-to",
        "keywords": ["enable", "disable", "toggle", "transport", "option", "on", "off", "hide"]
    },

    # ========== DEALER SCHEDULE (DETAILED HOW-TO) ==========
    {
        "question": "How do I increase dealer schedule capacity?",
        "answer": """To increase dealer schedule (store-level) capacity:

1. Go to Settings → Appointments → Dealer Schedule
2. You will see a grid view showing Sunday through Saturday
3. Each day shows the appointment capacity for that day
4. To increase capacity for a specific day:
   - Click on the day cell
   - Change the 'Total Maximum Appointments per day' value
   - You can also modify 'Total Maximum Appointments per slot'
5. For date-specific exceptions (e.g., holidays, special events):
   - Toggle 'Allow Changes Only for Selected Dates' at the top
   - This converts to a date-based view where you can set capacity for specific dates
6. Save your changes

IMPORTANT NOTES:
- The dealer schedule sets STORE-LEVEL capacity that applies to all advisors
- Individual advisor schedules cannot exceed the dealer schedule limits
- You cannot set different slot capacities within the same day here - use Capacity Rules for that
- Gray slots at the individual level mean they're blocked at the dealer level""",
        "category": "how-to",
        "keywords": ["increase", "dealer", "schedule", "capacity", "limit", "how to", "change", "modify", "day", "store", "dealership", "appts per day", "appt per slot", "settings", "saturday", "hours", "times"]
    },
    {
        "question": "How do I increase individual advisor schedule capacity?",
        "answer": """To increase an individual advisor's appointment capacity:

1. Go to Settings → Appointments → Individuals
2. Select the advisor from the dropdown list
3. You will see a grid view similar to the dealer schedule
4. To modify capacity:
   - Click on the day or slot you want to change
   - Adjust the appointment limit for that day
   - Toggle slots ON (green) or OFF (red) to enable/disable
5. For date-specific changes:
   - Toggle 'Allow Changes Only for Selected Dates' at the top
   - Set capacity for specific dates (e.g., vacation days, special schedules)
6. For recurring weekly schedules:
   - You can set up recurring patterns that repeat weekly
7. Save your changes

IMPORTANT NOTES:
- Gray slots mean they're disabled at the Dealer Schedule level - you cannot enable them here
- To enable a gray slot, you must first enable it in the Dealer Schedule
- Use this to block specific time slots like lunch hours (set to 0 capacity)
- Does NOT manage appointment assignment priorities - use Assignment Rules for that""",
        "category": "how-to",
        "keywords": ["increase", "individual", "advisor", "schedule", "capacity", "limit", "how to", "change", "modify", "adjust", "appointments per advisor", "maximum", "fix", "switch off", "off", "vacation", "recurring", "week of"]
    },
    {
        "question": "What's the difference between weekly and date-specific schedules?",
        "answer": "Weekly Schedule: Applies to all weeks by default - set limits once and they repeat every week. Date-Specific Schedule: Override the weekly schedule for specific calendar dates (holidays, special events, vacation). Important: Date-specific changes ALWAYS override the weekly schedule. Use the blue toggle bar at top of schedule view to switch between views.",
        "category": "concept",
        "keywords": ["weekly", "date-specific", "schedule", "override", "repeat", "recurring"]
    },
    {
        "question": "How do I set up recurring schedules that repeat every 2 or 3 weeks?",
        "answer": "For multi-week recurring schedules (beyond standard weekly): 1) Go to Settings > Appointments > Individuals Schedule, 2) Select the advisor, 3) Click the yellow 'Edit Recurring Schedules' button (if enabled), 4) Select the recurrence length in weeks (e.g., every 2 or 3 weeks), 5) Set the start date for the recurring schedule, 6) Modify slots and limits as needed, 7) Click Save. This feature requires enablement - contact support if you don't see the button.",
        "category": "how-to",
        "keywords": ["recurring", "multi-week", "2 weeks", "3 weeks", "rotation", "schedule", "repeat"]
    },
    {
        "question": "What do the slot colors mean in the schedule grid?",
        "answer": "Schedule grid slot colors: Green = slot is enabled and available for booking. Red = slot is manually disabled (no appointments allowed). Gray = slot is unavailable because it's disabled at a higher level (e.g., disabled in Dealer Schedule, or outside dealership hours). Gray slots cannot be enabled at the individual level until enabled at the dealer level first.",
        "category": "concept",
        "keywords": ["color", "green", "red", "gray", "slot", "schedule", "grid", "enabled", "disabled"]
    },
    {
        "question": "How do I select multiple slots at once in the schedule grid?",
        "answer": "To select multiple slots in schedule grid: Hold SHIFT to select multiple slots in adjoining rows/columns. Hold CONTROL (Ctrl) to select multiple separate/non-adjacent slots. Click the day name at the top of a column to toggle ALL slots for that entire day. This makes bulk enable/disable operations much faster.",
        "category": "how-to",
        "keywords": ["multiple", "select", "slots", "shift", "control", "bulk", "schedule", "grid"]
    },

    # ========== OPERATION/OPCODE CAPACITY ==========
    {
        "question": "How do I increase operation/opcode capacity limit?",
        "answer": """Opcode capacity can be configured in TWO places:

**Option 1: Direct Daily Limits (Scheduler Plus)**
1. Go to Settings → Appointments → Opcodes and Dealer Menus
2. Search for the specific opcode or click 'Add New'
3. Scroll to the bottom of the opcode settings
4. Set the 'Daily Limit' value for that opcode
5. Save - this limits how many times this service can be booked per day

**Option 2: Capacity Rules (for complex scenarios)**
1. Go to Settings → Appointments → Capacity Rules
2. Create a rule with IF condition matching the opcode/skill
3. Set THEN clause with the limit (e.g., Total Appointments <= X)
4. Use PER interval (Day, Hour, Slot) as needed

**When to use which:**
- Use Option 1 for simple daily limits per opcode
- Use Option 2 for complex scenarios: specific dates, specific slots, day-of-week restrictions, or combining with other conditions (teams, advisors, etc.)""",
        "category": "how-to",
        "keywords": ["increase", "operation", "opcode", "capacity", "limit", "how to", "change", "modify", "skill", "daily limit", "opcodes and dealer menus"]
    },
    {
        "question": "How can I limit service hours instead of appointment count?",
        "answer": "To limit by service hours: Create a capacity rule with THEN = 'Total Service Hours' instead of 'Total Appointments'. Example: 'IF Skill in Oil Change Bucket: Cars, Oil Change Bucket: Trucks THEN Total Service Hours <= 10 PER Day' - this limits total oil change work to 10 hours per day instead of counting individual appointments.",
        "category": "how-to",
        "keywords": ["service hours", "duration", "time", "hours", "limit", "capacity rule"]
    },

    # ========== TROUBLESHOOTING ==========
    {
        "question": "Why can't customers book appointments?",
        "answer": "Common reasons customers can't book: 1) Capacity is 0 (check limitInfo for limiting factor), 2) All slots are disabled in dealer/individual schedule (red or gray slots), 3) Transport option is disabled or at limit, 4) A capacity rule blocks that day/time/service, 5) Assignment rule doesn't route to any available advisor. Use get_capacity tool with includeLimitInfo=true to see the exact limiting factor.",
        "category": "troubleshooting",
        "keywords": ["can't book", "cannot book", "unable to book", "booking failed", "no availability", "blocked"]
    },
    {
        "question": "Why is the online scheduler showing no availability?",
        "answer": "Online scheduler may show no availability because: 1) Online Reserve limits are exhausted (separate from Total limits), 2) All slots for that day are disabled, 3) Capacity rules block online bookings, 4) Transport options available online are at capacity. Check Settings > Transport Options for 'Online Reserve' limits specifically - they reserve capacity for online customers only.",
        "category": "troubleshooting",
        "keywords": ["online", "scheduler", "no availability", "showing", "empty", "nothing available"]
    },
    {
        "question": "A rule isn't working, what should I check?",
        "answer": "If a capacity/assignment rule isn't working: 1) Check rule status - is it ACTIVE? 2) Check applicability clause - does the date/day match? 3) Check IF conditions - are ALL conditions met? (AND means all must be true), 4) Check operator - 'in' vs 'not in' semantics, 5) Verify entity names match exactly (case-sensitive for some fields). Use get_rules tool to see the full rule configuration including ifVerbiage and thenVerbiage.",
        "category": "troubleshooting",
        "keywords": ["rule", "not working", "doesn't work", "broken", "issue", "problem", "check"]
    },
    {
        "question": "Why is capacity different for dealer app vs online scheduler?",
        "answer": "Capacity can differ between dealer app and online scheduler because: 1) Online Reserve limits reserve capacity specifically for online customers, 2) If Online Reserve = 3 and Total = 10, dealership can book 10 but 3 are guaranteed for online, 3) Once Online Reserve is used, online customers see 0 availability even if dealer app shows remaining capacity. Check Settings > Transport Options > 'Online Reserve Limits' vs 'Total Limits'.",
        "category": "troubleshooting",
        "keywords": ["dealer app", "online", "different", "mismatch", "inconsistent", "capacity differs"]
    },
    {
        "question": "How do I find which rule is blocking appointments?",
        "answer": "To find the blocking rule: 1) Use get_capacity tool with the specific date/advisor/transport, 2) Check the limitInfo in the response, 3) Look at 'limitingFactor' field - if it says 'CAPACITY_RULE', the 'details' will show the rule name, 4) Go to Settings > Capacity Rules and search for that rule name to modify it.",
        "category": "troubleshooting",
        "keywords": ["find", "which", "rule", "blocking", "limiting", "identify", "source"]
    },
    {
        "question": "Why does one advisor have different capacity than another?",
        "answer": "Advisors can have different capacities because: 1) Individual schedule limits differ (Settings > Individuals), 2) They're on different teams with different capacity rules, 3) Capacity rules target specific advisors by name/UUID, 4) One advisor may have date-specific schedule overrides. Check both the individual schedule AND capacity rules that reference DEALER_ASSOCIATE_UUID to see advisor-specific limits.",
        "category": "troubleshooting",
        "keywords": ["advisor", "different", "capacity", "varies", "why", "not same"]
    },
    {
        "question": "Why are appointments showing a red warning sign (DMS push failure)?",
        "answer": """A red warning sign on appointments indicates a DMS push failure. The most common cause is that the assigned Service Advisor doesn't have a valid DMS ID configured.

**How to fix:**
1. Go to Manage Settings → Manage Users
2. Find the Service Advisor showing the warning
3. Verify they have a valid DMS ID entered
4. Add or correct the DMS ID if missing
5. Save - future appointments should push correctly

Note: Existing failed appointments may need to be manually retried or recreated.""",
        "category": "troubleshooting",
        "keywords": ["red warning", "DMS", "push failure", "sync", "error", "warning sign", "DMS ID", "exclamation"]
    },
    {
        "question": "How does 'No Preference' advisor assignment work?",
        "answer": """The 'No Preference' feature intelligently assigns appointments to service advisors when no specific advisor is selected.

**IMPORTANT: This is NOT a round-robin algorithm.** It's a load-balancing system based on capacity percentage.

**How It Works:**
When 'No Preference' is selected:
1. Scheduler evaluates all eligible advisors available for the selected date/time slot
2. Calculates each advisor's current capacity percentage (booked ÷ total capacity)
3. Assigns the appointment to the advisor with the LOWEST capacity percentage for that day
4. Advisors not available for that day/time are excluded from consideration

**Example:** If 3 advisors are booked at 70%, 60%, and 50% of their daily capacity, the appointment goes to the 50% advisor - ensuring fair workload distribution.

**Eligibility Conditions:**
- Only advisors marked available for the selected date/time are eligible
- If no advisors are available, the slot won't show in Consumer Scheduler
- Assignment won't occur if no advisor's availability includes the selected slot

**CS 4.0 Default:** 'No Preference' is ENABLED by default in Consumer Scheduler 4.0. If disabled, the system picks the first advisor on the list, causing all appointments to go to one advisor - this is problematic for dealerships!

**Enabling 'No Preference':**
Contact myKaarma support to enable or configure the 'No Preference' feature for your dealership.

**CRITICAL - Dummy Advisor Warning:**
Some dealerships used to create 'No Preference' as a dummy advisor with a DMS ID. The system now uses a blank/null DMS ID for proper load-balancing. If a DMS ID is assigned to the No Preference user, it behaves like a regular advisor and the load-balancing logic WILL NOT WORK.""",
        "category": "concept",
        "keywords": ["no preference", "advisor", "assignment", "any advisor", "automatic", "load balancing", "capacity percentage", "least occupied", "dummy advisor", "DMS ID", "CS 4.0", "consumer scheduler", "dealerapp", "workload distribution"]
    },
    {
        "question": "How do I close the scheduler for holidays or specific dates?",
        "answer": """To block appointments on holidays or specific dates:

1. Go to Settings → Appointments → Dealer Schedule
2. Toggle 'Allow changes for selected dates' at the top
3. Navigate to the specific date you want to block
4. Click on the date to turn all slots OFF (red), OR
5. Click individual time slots to disable only specific hours
6. Save your changes

This manually closes the scheduler for that day. For recurring closures (like every Sunday), use the weekly schedule view instead.""",
        "category": "how-to",
        "keywords": ["holiday", "holidays", "close", "closed", "block", "day off", "specific date", "christmas", "thanksgiving", "major dates", "vacation"]
    },
    {
        "question": "How do I show service prices on the online scheduler?",
        "answer": """To display service prices and descriptions to customers during online booking:

1. Go to Settings → Appointments → Opcodes and Dealer Menus
2. Select the opcode you want to configure
3. Enter the price and description fields
4. Save your changes

**Note:** Full activation of price display on the online scheduler may require support assistance to enable the feature for your dealership.""",
        "category": "how-to",
        "keywords": ["price", "prices", "cost", "description", "online scheduler", "display", "show", "customer facing", "opcode"]
    },

    # ========== NAVIGATION & UI ==========
    {
        "question": "Where do I find capacity rules settings?",
        "answer": "To access capacity rules: Settings (gear icon) > Capacity Rules. You'll see a list of all rules with their status (Active/Inactive), name, and summary. Click '+ Add Rule' to create new, or click an existing rule to edit. The Rules tab may also be called 'Rules Management' in some versions.",
        "category": "navigation",
        "keywords": ["where", "find", "capacity rules", "settings", "location", "navigate"]
    },
    {
        "question": "Where do I find transport option settings?",
        "answer": "To access transport options: Settings > Appointments > Transport Options. Top section shows the list of all transport options with enable/disable toggles. Bottom section (after selecting a transport option from dropdown) shows capacity limits per day and time blocks.",
        "category": "navigation",
        "keywords": ["where", "find", "transport", "options", "settings", "location", "navigate"]
    },
    {
        "question": "Where do I find dealer schedule settings?",
        "answer": "To access dealer schedule: Settings > Appointments > Dealer Schedule. You'll see a grid with days (columns) and time slots (rows). Use the toggle at top to switch between Weekly and Date-Specific views. This controls dealership-wide limits that override individual advisor schedules.",
        "category": "navigation",
        "keywords": ["where", "find", "dealer", "schedule", "settings", "location", "navigate"]
    },
    {
        "question": "Where do I find individual advisor schedule settings?",
        "answer": "To access individual advisor schedules: Settings > Appointments > Individuals. Select the advisor from the dropdown menu. The grid shows their personal schedule limits. Gray slots mean they're disabled at the dealer level and cannot be enabled here. Use the toggle for Weekly vs Date-Specific views.",
        "category": "navigation",
        "keywords": ["where", "find", "individual", "advisor", "schedule", "settings", "location", "navigate"]
    },
    {
        "question": "Where do I find assignment rules settings?",
        "answer": "To access assignment rules: Settings > Assignment Rules. Similar layout to capacity rules - you'll see a list of all assignment rules. Click '+ Add Rule' to create new ones. Remember: assignment rules control which options are AVAILABLE (filtering), while capacity rules control how MANY (limiting).",
        "category": "navigation",
        "keywords": ["where", "find", "assignment", "rules", "settings", "location", "navigate"]
    },

    # ========== ADVANCED CONCEPTS ==========
    {
        "question": "What is the priority order of limits?",
        "answer": "The system calculates all applicable limits and uses the MINIMUM (most restrictive): 1) Dealer Schedule Limit, 2) Individual Advisor Schedule Limit, 3) Capacity Rule Limit, 4) Transport Option Limit, 5) Opcode Daily Limit. The lowest becomes the 'effective limit' and is shown as the limiting factor in limitInfo. To increase capacity, you must increase the limiting factor specifically.",
        "category": "concept",
        "keywords": ["priority", "order", "limits", "minimum", "effective", "which", "override"]
    },
    {
        "question": "How do multiple capacity rules combine?",
        "answer": "Multiple capacity rules that match the same scenario combine by taking the MINIMUM limit. Each rule is evaluated independently, and the most restrictive one wins. Example: Rule A says 'Max 20 appointments for Main Shop' and Rule B says 'Max 10 appointments for Loaner'. If booking a loaner for Main Shop, the effective limit is min(20, 10) = 10.",
        "category": "concept",
        "keywords": ["multiple", "rules", "combine", "overlap", "interact", "conflict"]
    },
    {
        "question": "What happens when dealer schedule and individual schedule conflict?",
        "answer": "Dealer schedule ALWAYS overrides individual schedule. If a slot is disabled (red or gray) at the dealer level, it cannot be enabled for any individual advisor. The dealer schedule sets the maximum bounds, and individual schedules can only restrict further, not expand. Gray slots in individual schedule mean 'blocked at dealer level'.",
        "category": "concept",
        "keywords": ["conflict", "override", "dealer", "individual", "schedule", "precedence"]
    },
    {
        "question": "What is the difference between 'in' and 'in any' operators?",
        "answer": "Both match values in a list, but: 'in' typically matches exact containment in a single value, while 'in any' matches if the value is in ANY of the selected options. For multi-select fields like teams or skills, 'in any' is more common. Example: 'Transport Option in any [Loaner, Shuttle]' matches if the transport is Loaner OR Shuttle.",
        "category": "concept",
        "keywords": ["in", "in any", "operator", "difference", "match", "multiple"]
    },
    {
        "question": "What is INCLUSIVELY_MATCHES vs EXACTLY_MATCHES?",
        "answer": "Rule matching criteria: EXACTLY_MATCHES means all specified conditions must match exactly. INCLUSIVELY_MATCHES is more permissive - it includes the specified values but also matches broader scenarios. For capacity queries, INCLUSIVELY_MATCHES is typically used to get all relevant capacity including rules that may affect the requested entity indirectly.",
        "category": "concept",
        "keywords": ["inclusively", "exactly", "matches", "criteria", "matching", "rule"]
    },

    # ========== COMMON SCENARIOS ==========
    {
        "question": "How do I block all appointments on a holiday?",
        "answer": "To block appointments on a holiday: 1) Easiest: Go to Settings > Dealer Schedule, switch to Date-Specific view, select the holiday date, set all slots to OFF (red) or set Total appointments to 0. OR 2) Create a capacity rule: IF Date = [holiday date] THEN Total Appointments <= 0 PER Day. Method 1 is simpler for one-off dates; Method 2 is better if you want to preserve the rule for documentation.",
        "category": "how-to",
        "keywords": ["block", "holiday", "close", "closed", "day off", "no appointments"]
    },
    {
        "question": "How do I limit loaners to only certain advisors or teams?",
        "answer": "Use an assignment rule (not capacity rule): 1) Go to Settings > Assignment Rules, 2) Click '+ Add Rule', 3) IF Transport Option in Loaner, 4) THEN Teams in [specific teams] or Advisor in [specific advisors], 5) Activate and save. This ensures loaner appointments can only be assigned to specified teams/advisors. Note: This doesn't limit count, just routing.",
        "category": "how-to",
        "keywords": ["loaner", "limit", "certain", "specific", "only", "advisors", "teams", "restrict"]
    },
    {
        "question": "How do I set up express lane with limited services?",
        "answer": "For an express lane setup: 1) Create a team called 'Express Shop' with quick-service advisors, 2) Create assignment rule: IF Opcode Duration <= 30 (or specific opcodes) THEN Teams in Express Shop, 3) Create capacity rule: IF Teams in Express Shop THEN Total Appointments <= X PER Hour. This routes quick services to express team and limits their hourly volume.",
        "category": "how-to",
        "keywords": ["express", "lane", "quick", "service", "fast", "setup", "configure"]
    },
    {
        "question": "How do I allow unlimited capacity?",
        "answer": "To allow unlimited appointments: 1) Remove any capacity rules that restrict that entity, 2) Set high limits (like 999) in dealer/individual schedules, 3) Set high limits for transport options. Note: True 'unlimited' isn't recommended as it can cause overbooking. The system uses a very large number (Double.MAX_VALUE) internally to represent 'no limit set'. You'll see this as scientific notation (1.79e+308) in the response.",
        "category": "how-to",
        "keywords": ["unlimited", "no limit", "remove limit", "maximum", "infinite"]
    },
    {
        "question": "How do I copy a schedule from one advisor to another?",
        "answer": "Currently there's no direct 'copy schedule' feature. To replicate: 1) Note down the source advisor's limits from Settings > Individuals, 2) Select the target advisor, 3) Manually set the same values. For recurring schedules, you'll need to set up each advisor individually. Consider using teams and team-based capacity rules for consistent limits across multiple advisors.",
        "category": "how-to",
        "keywords": ["copy", "duplicate", "schedule", "advisor", "another", "same"]
    },
]


# Short summary version (for fast queries)
KNOWLEDGE_SUMMARY = """You are a capacity chatbot assistant. Key concepts:
- Capacity = max appointments per time period/advisor/team/transport
- Capacity Rules = define when/how many appointments (Applicability + If + Then clauses)
- Transport Options = ways customers get to/from service (Loaner, Shuttle, etc.)
- Teams = groups of advisors (Main Shop, Express Shop, etc.)
- Use get_rules tool to fetch current rules
- Use get_capacity tool to fetch current capacity data (includes actionable "HOW TO INCREASE CAPACITY" advice)
- Answer concept questions from knowledge, use tools for current data queries
- IMPORTANT: When users ask follow-up questions like "how do I increase it?", check previous tool responses for specific actionable advice before generating generic responses."""

# Additional knowledge documentation (can be expanded)
# NOTE: If you have the full KNOWLEDGE_DOCUMENTATION dict with all sections,
# it will be included when condensed=False
KNOWLEDGE_DOCUMENTATION: Dict[str, str] = {
    # Add your documentation sections here if needed
    # Example structure:
    # "capacity_concepts": "...",
    # "rule_structure": "...",
    # etc.
}

def get_knowledge_base_section(condensed: bool = True) -> str:
    """Generate the knowledge base section for the system prompt.

    Args:
        condensed: If True, use short summary. If False, include full Q&A list.
                   Default True for better performance.

    Returns:
        Formatted string containing knowledge base content
    """
    if condensed:
        # Use short summary for better latency
        return KNOWLEDGE_SUMMARY

    # Full knowledge base (only use when needed)
    sections = []

    # Add common questions
    sections.append("=== COMMON QUESTIONS & ANSWERS ===")
    sections.append("Users frequently ask these questions. Answer them directly using this knowledge (no API calls needed):")
    sections.append("")

    for i, qa in enumerate(COMMON_QUESTIONS, 1):
        sections.append(f"Q{i}: {qa['question']}")
        sections.append(f"A{i}: {qa['answer']}")
        sections.append("")

    # Add documentation sections (if available)
    if KNOWLEDGE_DOCUMENTATION:
        sections.append("=== ADDITIONAL KNOWLEDGE ===")
        for key, content in KNOWLEDGE_DOCUMENTATION.items():
            sections.append(content.strip())
            sections.append("")

    return "\n".join(sections)


def get_relevant_knowledge(user_query: str, max_items: int = 3) -> str:
    """Get only relevant knowledge base items based on user query.

    Uses keyword matching with scoring to find the most relevant Q&As.
    Prioritizes:
    1. Exact phrase matches in question
    2. How-to matches when user asks how-to
    3. Number of keyword matches
    4. Synonym expansion for better matching

    Args:
        user_query: User's query text
        max_items: Maximum number of Q&A items to include (default 3)

    Returns:
        Formatted string with relevant knowledge only
    """
    # Synonym mappings for query expansion
    SYNONYMS = {
        "waiter": ["will wait", "waiting"],
        "waiters": ["will wait", "waiting"],
        "appt": ["appointment", "appointments"],
        "appts": ["appointment", "appointments"],
        "advisor": ["service advisor", "SA"],
        "SA": ["service advisor", "advisor"],
        "adjust": ["change", "modify", "increase", "decrease"],
        "fix": ["change", "modify", "correct"],
        "restrict": ["block", "limit", "disable"],
        "rideshare": ["uber", "lyft", "ride share"],
        "loaners": ["loaner", "loaner car", "loaner vehicle"],
        "slots": ["slot", "time slot", "time slots", "appointments"],
        "saturday": ["sat", "saturdays"],
        "sunday": ["sun", "sundays"],
        "mainshop": ["main shop"],
        "rotate": ["rotation", "rotation shop"],
    }

    query_lower = user_query.lower().strip()

    # Expand query with synonyms
    expanded_query = query_lower
    for word, synonyms in SYNONYMS.items():
        if word in query_lower:
            # Add synonyms to the query for matching
            expanded_query += " " + " ".join(synonyms)

    query_words = set(word for word in expanded_query.split() if len(word) > 2)

    # Detect if user is asking a how-to question
    is_how_to_query = any(phrase in query_lower for phrase in [
        "how do i", "how to", "how can i", "how should i",
        "increase", "change", "modify", "enable", "disable", "add", "create"
    ])

    scored_items = []

    for qa in COMMON_QUESTIONS:
        question_lower = qa.get("question", "").lower()
        qa.get("answer", "").lower()
        keywords = [k.lower() for k in qa.get("keywords", [])]
        category = qa.get("category", "")

        score = 0

        # Exact phrase match in question (highest priority)
        if query_lower in question_lower or question_lower in query_lower:
            score += 100

        # Check for multi-word phrase matches (e.g., "transport option")
        for phrase_len in [3, 2]:
            query_split = query_lower.split()
            for i in range(len(query_split) - phrase_len + 1):
                phrase = " ".join(query_split[i:i+phrase_len])
                if phrase in question_lower:
                    score += 20 * phrase_len

        # Keyword matches - count how many keywords match
        keyword_matches = sum(1 for kw in keywords if kw in query_lower)
        score += keyword_matches * 10

        # Word overlap with question
        question_words = set(word for word in question_lower.split() if len(word) > 2)
        word_overlap = len(query_words & question_words)
        score += word_overlap * 5

        # Boost how-to category when user asks how-to
        if is_how_to_query and category == "how-to":
            score += 30

        # Boost if "increase" appears in both query and question
        if "increase" in query_lower and "increase" in question_lower:
            score += 50

        if score > 0:
            scored_items.append((score, qa))

    # Sort by score descending
    scored_items.sort(key=lambda x: x[0], reverse=True)

    # Take top items
    relevant_items = [qa for score, qa in scored_items[:max_items]]

    if not relevant_items:
        # Fallback to summary if no matches
        return ""

    # Format relevant items
    sections = ["=== RELEVANT KNOWLEDGE ==="]
    for i, qa in enumerate(relevant_items, 1):
        sections.append(f"Q{i}: {qa['question']}")
        sections.append(f"A{i}: {qa['answer']}")
        sections.append("")

    return "\n".join(sections)


def get_question_examples() -> str:
    """Get example questions users might ask.

    Returns:
        Formatted string with example questions
    """
    questions = [qa["question"] for qa in COMMON_QUESTIONS]
    return "\n".join([f"- {q}" for q in questions[:10]])  # Show first 10 as examples


# You can extend this by loading from external files
def load_knowledge_from_file(file_path: str) -> None:
    """Load additional knowledge from a file (e.g., markdown, JSON).

    Args:
        file_path: Path to knowledge file
    """
    # TODO: Implement file loading if needed
    pass
