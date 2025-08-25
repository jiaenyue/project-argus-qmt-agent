# Requirements Document

## Introduction

This spec addresses the xtdata integration issues in the historical K-line tutorial. The current implementation has incorrect parameter usage for the `get_market_data` function and needs to be fixed to properly integrate with the real xtdata API instead of falling back to mock data.

## Requirements

### Requirement 1

**User Story:** As a developer using the tutorial, I want the xtdata integration to work correctly so that I can see real data comparison between API and local library.

#### Acceptance Criteria

1. WHEN calling xtdata.get_market_data THEN the function SHALL use correct parameter names and order as specified in the xtdata documentation
2. WHEN the xtdata call succeeds THEN the tutorial SHALL display real data from xtdata
3. WHEN the xtdata call fails THEN the tutorial SHALL provide clear error messages and graceful fallback

### Requirement 2

**User Story:** As a developer, I want the tutorial to handle both successful and failed xtdata calls gracefully so that the tutorial continues to run regardless of xtdata availability.

#### Acceptance Criteria

1. WHEN xtdata is not available THEN the tutorial SHALL continue with mock data and inform the user
2. WHEN xtdata returns empty data THEN the tutorial SHALL handle this case without crashing
3. WHEN xtdata parameters are incorrect THEN the tutorial SHALL catch the error and provide helpful debugging information

### Requirement 3

**User Story:** As a developer, I want to see proper data format handling so that both API and xtdata results can be compared meaningfully.

#### Acceptance Criteria

1. WHEN both API and xtdata return data THEN the tutorial SHALL format both datasets consistently for comparison
2. WHEN displaying comparison results THEN the tutorial SHALL show meaningful metrics like data count, date ranges, and sample values
3. WHEN data formats differ THEN the tutorial SHALL normalize them for proper comparison