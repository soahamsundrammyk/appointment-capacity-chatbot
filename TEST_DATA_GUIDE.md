# Test Data Guide for LangGraph Studio Testing

## Problem

When testing in LangGraph Studio (`langgraph dev`), you don't have the appointment-ui-client to provide cached data (transport options, advisors, teams). This data is needed for:
- UUID-to-name mapping
- Answering questions about available options
- Tool calls that use advisor/transport names

## Solution

The code now automatically loads **test data** when `cached_data` is not provided. This works seamlessly in both:
- **LangGraph Studio** (dev/testing) - Uses test data automatically
- **Production** (with UI) - Uses real data from appointment-ui-client

## How It Works

1. **Automatic Detection**: The code checks if `cached_data` is None
2. **Test Data Loading**: If missing, it loads test data (only in dev mode)
3. **Seamless Integration**: Works exactly like real cached data

## Configuration

### Option 1: Use Default Test Data (Easiest)

Just run `langgraph dev` - test data will be loaded automatically!

The default test data includes:
- **Transport Options**: Loaner, Shuttle, Rental, Will Wait, Pickup and Delivery
- **Advisors**: Vishal, Art, Martin, Sri, Alice
- **Teams**: Express Shop, Main Shop, Rotation Shop

### Option 2: Custom Test Data File

Create a JSON file with your actual data:

1. **Copy the example**:
   ```bash
   cp test_data_example.json test_data.json
   ```

2. **Edit `test_data.json`** with your real UUIDs:
   ```json
   {
     "transport_options": [
       {
         "uuid": "your-actual-loaner-uuid",
         "optionName": "Loaner",
         "customName": "Loaner"
       }
     ],
     "advisors": [
       {
         "uuid": "your-actual-vishal-uuid",
         "firstName": "Vishal",
         "lastName": "Sharma",
         "nickname": "Vishal"
       }
     ],
     "teams": [
       {
         "uuid": "your-actual-express-shop-uuid",
         "name": "Express Shop",
         "dealerAssociateUuids": ["your-actual-vishal-uuid"]
       }
     ]
   }
   ```

3. **Set environment variable**:
   ```bash
   export TEST_DATA_PATH=./test_data.json
   langgraph dev
   ```

### Option 3: Environment Variable Control

Force test data usage (even in production-like environments):
```bash
USE_TEST_DATA=true langgraph dev
```

## Getting Real UUIDs

To get your actual UUIDs for the test data file:

1. **From Browser DevTools** (when using appointment-ui-client):
   - Open browser DevTools (F12)
   - Go to Network tab
   - Look for API calls that return advisors/teams/transport options
   - Copy the UUIDs from the response

2. **From API Directly**:
   ```bash
   # Get advisors
   curl 'https://your-dealer.mykaarma.dev/api/advisors' \
     -H 'Cookie: mkid=your-mkid'
   
   # Get teams
   curl 'https://your-dealer.mykaarma.dev/api/teams' \
     -H 'Cookie: mkid=your-mkid'
   
   # Get transport options
   curl 'https://your-dealer.mykaarma.dev/api/transport-options' \
     -H 'Cookie: mkid=your-mkid'
   ```

3. **From LangSmith Traces**:
   - Check previous successful runs
   - Look at the `cached_data` in the state
   - Copy UUIDs from there

## Testing

### Test 1: Basic Query (No Cached Data Needed)
```
Query: "can you please fetch rules"
Expected: Works fine, doesn't need cached data
```

### Test 2: Query Using Advisor Name
```
Query: "show me capacity for vishal"
Expected: 
- If test data has "Vishal" → Works! Maps name to UUID
- If no test data → May fail or use UUID directly
```

### Test 3: Query About Available Options
```
Query: "what transport options are there?"
Expected:
- With test data → Lists: Loaner, Shuttle, Rental, etc.
- Without test data → May say "I don't have that information"
```

## Best Practices

1. **Use Real UUIDs**: For accurate testing, use your actual UUIDs in `test_data.json`
2. **Keep It Updated**: Update test data when your advisors/teams change
3. **Don't Commit Real Data**: Add `test_data.json` to `.gitignore` if it contains real UUIDs
4. **Use Defaults for Quick Tests**: Default test data is fine for basic functionality testing

## File Structure

```
capacity-chatbot-service/
├── test_data_example.json          # Template (safe to commit)
├── test_data.json                  # Your actual data (add to .gitignore)
├── src/capacity_chatbot/
│   └── utils/
│       └── test_data.py            # Test data loading logic
└── .env                            # Can set TEST_DATA_PATH here
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `USE_TEST_DATA` | Force use of test data | `false` (auto-detects) |
| `TEST_DATA_PATH` | Path to custom test data JSON file | Uses default test data |

## Troubleshooting

### Test data not loading?
- Check: Is `USE_TEST_DATA=true` set? (or running `langgraph dev` locally)
- Check: Does `test_data.json` exist if `TEST_DATA_PATH` is set?
- Check: Is the JSON file valid? (use `python -m json.tool test_data.json`)

### Wrong UUIDs being used?
- Update `test_data.json` with correct UUIDs
- Restart `langgraph dev` to reload

### Want to disable test data?
- Set `USE_TEST_DATA=false` in environment
- Or ensure `cached_data` is always provided in the input

## Example: Complete Setup

1. **Create test data file**:
   ```bash
   cp test_data_example.json test_data.json
   # Edit with your real UUIDs
   ```

2. **Add to .env** (optional):
   ```bash
   TEST_DATA_PATH=./test_data.json
   USE_TEST_DATA=true
   ```

3. **Run**:
   ```bash
   langgraph dev
   ```

4. **Test**:
   - "what transport options are there?" → Should list your options
   - "show me capacity for vishal" → Should work if Vishal UUID is correct

That's it! Test data is now automatically available in LangGraph Studio! 🎉

