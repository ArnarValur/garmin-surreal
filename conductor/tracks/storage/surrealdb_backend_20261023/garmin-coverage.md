# Garmin coverage audit — 2026-10-23

> Agent report (read of garminconnect 0.3.7 + upstream code, no live calls). Items marked unverified need the capability probe: scripts/garmin_capability_probe.py.

GARMIN COVERAGE REPORT: what upstream garmin-grafana does not fetch

Scope and sources
- I installed garminconnect 0.3.7 in a Python 3.13 venv at /tmp/claude-1000/-home-solmundur-Projects/7211be9d-d6b0-4eec-9a37-39bad1f7d3e0/scratchpad/coverage/.venv. I read the installed `Garmin` class and `typed.py`, and grepped `src/garmin_grafana/*.py` in the repo.
- No Garmin login and no live API calls.
- Response field names for sleep, HRV and daily stats are confirmed from the `typed.py` pydantic models. Everything marked "(unverified)" comes from community knowledge of the Garmin payloads. Check it against a real response before building on it.
- I could not verify Venu 2 Plus feature support against Garmin's documentation. Those judgements are from memory, so treat them as likely. The only reliable test is to log which methods return data (see recommendation 1).

0. WHAT UPSTREAM ALREADY USES (garmin_fetch.py)

Default FETCH_SELECTION (line 62): daily_avg, sleep, steps, heartrate, stress, breathing, hrv, fitness_age, vo2, activity, race_prediction, body_composition, lifestyle.
Off by default: lactate_threshold, training_status, training_readiness, hill_score, endurance_score, blood_pressure, hydration, solar_intensity, cycling_dynamics.

| Method called | Gate | Measurement |
|---|---|---|
| get_stats | daily_avg | DailyStats |
| get_sleep_data | sleep | SleepSummary, SleepIntraday |
| get_steps_data | steps | StepsIntraday |
| get_heart_rates | heartrate | HeartRateIntraday |
| get_stress_data (called twice, same URL) | stress | StressIntraday, BodyBatteryIntraday |
| get_respiration_data | breathing | BreathingRateIntraday |
| get_hrv_data | hrv | HRV_Intraday |
| get_fitnessage_data | fitness_age | FitnessAge |
| get_max_metrics | vo2 | VO2_Max |
| get_race_predictions(daily) | race_prediction | RacePredictions |
| get_weigh_ins | body_composition | BodyComposition |
| get_lifestyle_logging_data | lifestyle | LifestyleJournal |
| get_activities_by_date | activity | ActivitySummary |
| get_activity_hr_in_timezones | activity | Zone boundaries in ActivitySummary; StrengthHRZones |
| get_activity_exercise_sets | activity (strength only) | StrengthExerciseSet |
| download_activity ORIGINAL (FIT), TCX fallback | activity | ActivityGPS, ActivitySession, ActivityLap, ActivityLength; cycling dynamics also needs cycling_dynamics |
| connectapi biometric-service/stats lactateThreshold* (raw URL, not get_lactate_threshold) | lactate_threshold | LactateThreshold |
| get_training_status | training_status | TrainingStatus |
| get_training_readiness | training_readiness | TrainingReadiness |
| get_hill_score | hill_score | HillScore |
| get_endurance_score | endurance_score | EnduranceScore |
| get_blood_pressure | blood_pressure | BloodPressure |
| get_hydration_data | hydration | Hydration |
| get_device_solar_data | solar_intensity | SolarIntensity |
| get_device_last_used | always | DeviceSync; also drives the sync loop |
| get_last_activity | startup | Timezone detection only |
| connectapi POST wellness/epoch/request | REQUEST_INTRADAY_DATA_REFRESH | None (data refresh) |

Zero-code win: for "everything", add `hydration`, `training_status`, `training_readiness`, `endurance_score`, `hill_score` and `lactate_threshold` to FETCH_SELECTION. These are already implemented. Some will simply return nothing on a Venu 2 Plus.
- `solar_intensity` is useless on this watch (no solar).
- `blood_pressure` only has data if he logs manually or owns a Garmin Index BPM, which is a different device from the scale.

(a) TABLE OF UNUSED DATA METHODS

The "Relevance" column is for a Venu 2 Plus plus an Index scale. "Cadence" says whether the data is per-date, a range, or a one-off.

| Method (args) | Endpoint | Returns | Cadence | Relevance | Reason |
|---|---|---|---|---|---|
| get_spo2_data(cdate) | wellness-service/wellness/daily/spo2/{d} | All-day Pulse Ox: avg, lowest, 7-day avg, latest, hourly averages, intraday readings (unverified) | per-date | HIGH | Upstream stores only sleep SpO2 plus daily avg/lowest. All-day intraday SpO2 is a gap. The watch has Pulse Ox; it needs All-Day mode enabled. |
| get_body_battery_events(cdate) | wellness-service/wellness/bodyBattery/events/{d} | List of events (sleep, activity, nap, auto-detected) with Body Battery impact and feedback (unverified) | per-date | HIGH | What charged or drained the battery, per event. Not derivable from the intraday curve. |
| get_body_battery(start, end) | wellness-service/wellness/bodyBattery/reports/daily | Per-day charged, drained, plus the values array; range-capable | range | MEDIUM | Same curve upstream already gets via get_stress_data. Useful as a one-call backfill and for charged/drained. |
| get_all_day_events(cdate) | wellness-service/wellness/dailyEvents | Auto-detected activities not recorded on the watch (walks and similar) | per-date | MEDIUM | Captures movement the watch detected without a started activity. |
| get_floors(cdate) | wellness-service/wellness/floorsChartData/daily/{d} | 15-min buckets of floors climbed and descended | per-date | MEDIUM | Venu 2 Plus has a barometer. Upstream keeps only daily floor totals. |
| get_intensity_minutes_data(cdate) | wellness-service/wellness/daily/im/{d} | Moderate and vigorous minutes, weekly goal, goal progress | per-date | LOW-MED | Daily moderate/vigorous already in DailyStats. Adds the weekly goal and possibly intraday. |
| get_heart_rate_zones() | biometric-service/heartRateZones | Configured HR zones per sport, max HR, resting HR | one-off, snapshot on change | MEDIUM | Context for activity zones. Upstream stores zone boundaries only per activity. |
| get_user_profile() | userprofile-service/userprofile/user-settings | Profile: birth date, sex, height, weight, VO2max, lactate threshold, sleep/wake times, unit settings (unverified) | one-off, snapshot on change | MEDIUM | Config and age context; changes over time. |
| get_userprofile_settings() | userprofile-service/userprofile/settings | More user settings | one-off | LOW | Mostly UI preferences. |
| get_devices() | device-service/deviceregistration/devices | Registered devices: model, ids, details (unverified) | one-off | MEDIUM | Device inventory for scale and watch; shows the watch/scale pairing. |
| get_device_settings(device_id) | device-service/deviceservice/device-info/settings/{id} | Watch settings, alarms | one-off | LOW | Config only. |
| get_primary_training_device() | web-gateway/device-info/primary-training-device | Which device is primary | one-off | LOW | Only matters with multiple watches. |
| get_device_alarms() | via get_devices and get_device_settings | Active alarms | one-off | NONE | Not health data. |
| get_activity_weather(activity_id) | activity-service/activity/{id}/weather | Temperature, humidity, wind at the activity | per-activity | HIGH (outdoor) | One call per activity; no FIT equivalent. |
| get_activity(activity_id) | activity-service/activity/{id} | Full summary: metadata, device, gear, summaryDTO with extra metrics | per-activity | MEDIUM | List endpoint upstream uses is a subset. |
| get_activity_details(activity_id, maxchart, maxpoly) | activity-service/activity/{id}/details | Time series per metric, polyline | per-activity | LOW | FIT already parsed upstream. |
| get_activity_splits / get_activity_typed_splits / get_activity_split_summaries | activity-service/activity/{id}/splits, /typedsplits, /split_summaries | Laps and splits, per-km summaries | per-activity | LOW | FIT laps already stored as ActivityLap. |
| get_activity_power_in_timezones(activity_id) | .../powerTimeInZones | Power zones | per-activity | NONE | No power meter on a watch. |
| get_activity_gear(activity_id) | gear-service/gear/filterGear?activityId= | Gear used for an activity | per-activity | MEDIUM | Shoes/bike linked to activities. |
| get_gear(userProfilePK) / get_gear_stats(uuid) / get_gear_defaults / get_gear_activities | gear-service/gear/... | Gear list, mileage per piece, default assignments | one-off / periodic | MEDIUM | Shoe mileage tracking. |
| get_personal_record() | personalrecord-service/personalrecord/prs/{name} | PRs: fastest 5k/10k, longest run, most steps and similar (unverified) | one-off, periodic | MEDIUM | Trophy data not derivable from stored rows. |
| get_progress_summary_between_dates(start, end, metric, groupby) | fitnessstats-service/activity | Aggregated totals by activity type | range | LOW | Derivable from stored activities. |
| get_activity_types() | activity-service/activity/activityTypes | Type id and key map | one-off | LOW | Lookup table. |
| get_activities(start, limit, type) / count_activities() | activitylist-service/activities/search/activities, /count | Paged activity list, total count | one-off | NONE | Same data as get_activities_by_date. |
| get_activities_fordate(fordate) | mobile-gateway/heartRate/forDate/{d} | Mobile-gateway day payload | per-date | LOW | Odd endpoint; probably redundant. |
| download_activity GPX / KML / CSV | download-service/export/{gpx,kml,csv}/activity/{id} | Alternate exports | per-activity | NONE | FIT is a superset. |
| get_daily_steps(start, end) | usersummary-service/stats/steps/daily/{s}/{e} | Per-day steps, distance, step goal; 28-day chunks | range | LOW-MED | Covered by DailyStats, but fast for backfill and carries the step goal. |
| get_weekly_steps / get_weekly_stress / get_weekly_intensity_minutes | usersummary-service/stats/{steps,stress,im}/weekly/... | Weekly aggregates | range | LOW | Derivable from daily data. |
| get_rhr_day(cdate) | userstats-service/wellness/daily/{name} | Resting HR | per-date | LOW | Already in DailyStats.restingHeartRate and SleepSummary. |
| get_body_composition(start, end) | weight-service/weight/dateRange | Same weigh-ins plus totalAverage | range | LOW | Same data as get_weigh_ins. |
| get_daily_weigh_ins(cdate) | weight-service/weight/dayview/{d} | Day view of weigh-ins | per-date | LOW | Duplicate. |
| get_stats_and_body(cdate) | composite | get_stats merged with body composition | per-date | NONE | Composite of existing calls. |
| get_all_day_stress(cdate) | wellness-service/wellness/dailyStress/{d} | Same URL as get_stress_data | per-date | NONE | Pure alias. |
| get_user_summary(cdate) | usersummary-service/usersummary/daily/{name} | get_stats is an alias | per-date | NONE | Alias. |
| get_morning_training_readiness(cdate) | filters get_training_readiness | Morning reading only | per-date | NONE | Derived from a call upstream already makes. |
| get_lactate_threshold(latest/range) | biometric-service/... | LTHR, speed, power, daily/weekly/monthly | range or latest | LOW | Upstream uses the raw URL under the flag. Running only. |
| get_cycling_ftp() | biometric-service/biometric/latestFunctionalThresholdPower/CYCLING | FTP | one-off | NONE | No power meter. |
| get_power_zones() / get_power_zones_for_sport(sport) | biometric-service/powerZones/... | Power zones | one-off | NONE | No power. |
| get_running_tolerance(start, end, aggregation) | metrics-service/metrics/runningtolerance/stats | Running load tolerance | range | LOW | Needs newer running devices (unverified). |
| get_goals(status) | goal-service/goal/goals | Active, future, past goals | one-off | LOW-MED | Records his own targets. |
| get_earned_badges / get_available_badges / get_in_progress_badges / get_adhoc_challenges / get_badge_challenges / get_available_badge_challenges / get_non_completed_badge_challenges / get_inprogress_virtual_challenges | badge-service, adhocchallenge-service, badgechallenge-service | Gamification | one-off | LOW | Completeness only. |
| get_workouts / get_workout_by_id / get_scheduled_workouts(year, month) / get_scheduled_workout_by_id / get_training_plans / get_training_plan_by_id / get_adaptive_training_plan_by_id | workout-service, calendar-service, trainingplan-service | Planned workouts and plans | one-off, monthly | LOW | Planned-versus-done only if he uses plans. |
| get_nutrition_daily_food_log / get_nutrition_daily_meals / get_nutrition_daily_settings (cdate) | nutrition-service/food/logs, /meals, /settings | Calories and meals | per-date | LOW (unverified) | Only if he logs food in Connect. |
| get_golf_summary / get_golf_scorecard / get_golf_shot_data / get_golf_club_stats / get_golf_user_stats | gcs-golfcommunity/api/v2/... | Golf rounds | one-off | LOW | Venu 2 Plus has a golf app. Ask whether he golfs. |
| get_menstrual_data_for_date / get_menstrual_calendar_data / get_pregnancy_summary | periodichealth-service/menstrualcycle/... | Cycle tracking | n/a | NONE | Not applicable. |
| query_garmin_graphql(query) | graphql-gateway/graphql | Arbitrary GraphQL | ad hoc | UNKNOWN | Worth exploring. Example queries ship in the library's repo example.py, not in the installed wheel. |
| Write and admin methods | | add_*, set_*, delete_*, upload_*, schedule_*, request_reload, import_activity, create_manual_activity | | NONE | Not data fetches. |

Not exposed by the API:
- Health Snapshot (2-minute session). No dedicated method; maybe via GraphQL.
- Incident detection and phone calls leave no data in Connect.
- Raw all-day monitoring FIT files cannot be downloaded through garminconnect. They are available from Garmin's account-level data export (garmin.com/account/datamanagement). That is the fallback for literally everything, and the repo's garmin_bulk_importer.py already reads part of it.

(b) FIELDS DROPPED FROM ENDPOINTS UPSTREAM ALREADY FETCHES

1. get_stats / DailyStats (upstream lines 212-287)
   Kept: active/BMR kcal, steps, distance, activity-time seconds, moderate/vigorous minutes, floors (4 fields), HR min/max/resting/minAvg/maxAvg, skin-temp deviation, the stress duration and percentage fields, the six Body Battery fields, and averageSpo2/lowestSpo2.
   Dropped, confirmed from the typed.py DailyStats model:
   - averageStressLevel and maxStressLevel. These are the headline daily stress numbers and are not stored.
   - totalKilocalories and wellnessKilocalories.
   - dailyStepGoal.
   Dropped, unverified payload fields: intensityMinutesGoal, floor goal, latestSpo2 and its time, avg/high/low/latest respiration (avgWaking, highest, lowest), bodyBatteryMostRecentValue, stressQualifier, measurableAwake/Asleep duration, wellnessDistance, abnormalHeartRateAlertsCount, averageMonitoringEnvironmentAltitude, lastSyncTimestampGMT.
   Quirk: the point is written only when wellnessStartTimeGmt is set and the date is before today, so today's partial stats never land.

2. get_sleep_data / SleepSummary (upstream lines 317-500)
   Kept: stage seconds, SpO2 avg/low/high, respiration avg/low/high, awakeCount, avgSleepStress, overall sleepScore only, restlessMomentsCount, avgOvernightHrv, bodyBatteryChange, restingHeartRate, skin temp deviation. Intraday: movement, stage levels, restless, SpO2, respiration, HR, stress, Body Battery and HRV. The time is the sleep END timestamp.
   Dropped, confirmed from typed.py:
   - The seven sleep sub-scores: totalDuration, stress, awakeCount, remPercentage, restlessness, lightPercentage, deepPercentage. Each has a value and a qualifierKey such as EXCELLENT, GOOD or FAIR.
   - The overall score's qualifierKey.
   - napTimeSeconds.
   - sleepStartTimestampGMT/Local. Only the end time is stored, so bedtime is lost.
   - sleepWindowConfirmed.
   - avgSleepHRV (the DTO field, distinct from the top-level avgOvernightHrv).
   Dropped, unverified:
   - sleepScoreFeedback, sleepScoreInsight, sleepScorePersonalizedInsight.
   - sleepNeed (baseline and actual) and nextSleepNeed. The Sleep Coach on the Venu 2 series produces these.
   - The naps array.
   - unmeasurableSleepSeconds.
   - averageSpO2HRSleep.
   - hrvStatus text.
   - breathingDisruptionSeverity and breathingDisruptionData.
   - skinTempDataExists.
   - wellnessEpochRespirationAveragesList.
   Recommended: new fields on SleepSummary for the sub-scores, bedtime and sleep need. Upstream's existing HRV and skin-temp fields suggest the author targets newer watches. If the Venu 2 Plus does not produce them they will be null.

3. get_hrv_data
   Upstream keeps only hrvReadings (5-minute overnight values) and drops the whole hrvSummary, confirmed from typed.py:
   - weeklyAvg
   - lastNightAvg
   - status (BALANCED, UNBALANCED, LOW, POOR)
   - feedbackPhrase
   - baseline: lowUpper, balancedLow, balancedUpper, markerValue
   - sleepStart/EndTimestampGMT and the other timestamp fields.
   HRV status on the Venu 2 Plus is the open question. If get_hrv_data returns None or empty for his account, then neither the readings nor the summary exist. A hrvSummary gap is only worth fixing if the readings are non-empty.

4. get_stress_data
   - The whole payload is fetched twice. A single call would suffice, and caching the result would halve the cost.
   - Dropped: the summary stress fields (avg and max stress level), stressChartValueOffset, and the stressValueDescriptors. In bodyBatteryValuesArray each row is [ts, status, level, version]; upstream keeps only the level and drops status and version (unverified layout).

5. get_heart_rates
   - Dropped: lastSevenDaysAvgRestingHeartRate, maxHeartRate, minHeartRate and the descriptors (unverified).

6. get_respiration_data
   - Dropped: avgWakingRespirationValue, avgSleepRespirationValue, highestRespirationValue, lowestRespirationValue (unverified).

7. get_steps_data (dailySummaryChart)
   - Dropped: primaryActivityLevel and activityLevelConstant (sedentary/active/highly-active per 15 minutes).

8. get_weigh_ins (Index scale)
   - Kept: weight (grams), bmi, bodyFat, bodyWater, boneMass, muscleMass, physiqueRating, visceralFat.
   - Dropped: metabolicAge. The line is commented out and treats it as a millisecond timestamp, which is probably wrong. Store the plain number.
   - Also dropped (unverified): the per-day weightDelta, the range totalAverage, samplePk, and calendarDate.
   - Efficiency: upstream makes one call per day. get_weigh_ins takes a range, so one call could cover a backfill.

9. get_activities_by_date / ActivitySummary
   - Kept: a fixed list of about 35 fields.
   - Dropped (unverified): avgRespirationRate, min/maxRespirationRate, differenceBodyBattery, trainingEffectLabel, steps, avgRunCadence, maxRunCadence, strideLength, avgVerticalOscillation, groundContactTime, min/maxTemperature, avgPower/maxPower/normPower, start and end lat/lon, min/maxElevation, fastest splits, sportTypeId, eventType, timeZoneId, manufacturer, favorite, pr and purposeful flags, waterEstimated.
   - A raw-JSON mirror of the whole activity object is the cheapest way to avoid this loss.

10. get_training_status
    - Dropped (unverified): VO2max block, mostRecentTrainingLoadBalance (monthly low/high aerobic and anaerobic load), and heat and altitude acclimation. Only applicable if the Venu 2 Plus produces training status.

11. get_training_readiness
    - Dropped: feedbackLong, feedbackShort, inputContext (AFTER_WAKEUP_RESET separates the morning score from later ones), recovery-time change phrase, and the *FactorFeedback strings. Confirmed from typed.py.

12. get_race_predictions
    - Dropped: per-distance details beyond the four times (unverified).

13. get_hydration_data
    - Captured: valueInML, goalInML, sweatLossInML, activityIntakeInML.
    - Not captured: nothing known. It is gated off by default.

(c) TOP-10 RECOMMENDED ADDITIONS, RANKED BY VALUE

1. Capability probe. Do this first.
   - Method: a one-off script that, for one recent date, calls every method in the table and logs "returned data" or "empty" per method.
   - Params: the date of a recent sleep night; no args for the one-offs.
   - Output: a JSON summary rather than a DB measurement. It settles every "unverified" above for his devices and stops us building loaders that never fire.

2. All-day SpO2.
   - Method: get_spo2_data(cdate)
   - Params: `YYYY-MM-DD`
   - Measurement: SpO2Intraday (reading per timestamp) plus SpO2Daily (average, lowest, 7-day average, latest).
   - Gate: new flag `spo2`.

3. Body Battery events.
   - Method: get_body_battery_events(cdate)
   - Params: `YYYY-MM-DD`
   - Measurement: BodyBatteryEvent (tags: eventType; fields: impact, duration, feedback).

4. Sleep detail on the existing endpoint. No new call.
   - Method: reuse get_sleep_data
   - Fields to add to SleepSummary: seven sub-scores plus qualifiers, bedtime (sleepStartTimestampGMT), napTimeSeconds, sleepNeed, nextSleepNeed, score feedback and insight, hrvStatus, breathingDisruptionSeverity.

5. Daily stress and kcal totals. No new call.
   - Method: reuse get_stats
   - Add to DailyStats: averageStressLevel, maxStressLevel, totalKilocalories, dailyStepGoal, intensityMinutesGoal, and the avg/high/low respiration fields.

6. HRV summary and status. No new call.
   - Method: reuse get_hrv_data
   - Measurement: HRV_Summary (weeklyAvg, lastNightAvg, status, baseline bounds, feedbackPhrase), one point per date.
   - Only worthwhile if the probe shows the summary is populated on the Venu 2 Plus.

7. Activity weather.
   - Method: get_activity_weather(activity_id)
   - Params: each outdoor activity id (activities with GPS)
   - Measurement: ActivityWeather (temperature, humidity, wind), keyed by the same ActivityID tag as ActivitySummary.

8. Floors intraday.
   - Method: get_floors(cdate)
   - Params: `YYYY-MM-DD`
   - Measurement: FloorsIntraday (15-minute ascended and descended).

9. Profile, zones and device snapshots.
   - Methods: get_user_profile(), get_heart_rate_zones(), get_devices()
   - Params: none
   - Measurement: UserProfileSnapshot and HeartRateZoneConfig, written on change; DeviceInventory once.

10. Gear, personal records and goals.
    - Methods: get_gear + get_gear_stats(uuid), get_personal_record(), get_goals(status="active")
    - Params: userProfilePK from the profile; none; status
    - Measurements: GearStats, PersonalRecord, Goal.

Other quick wins that need no new code:
- Switch on `hydration`, `training_status`, `training_readiness`, `endurance_score` and `hill_score` in FETCH_SELECTION. Some of them may not apply to the Venu 2 Plus; the probe in 1 will say which.
- Collapse the duplicated get_stress_data call.
- Use range endpoints (get_weigh_ins, get_daily_steps, get_body_battery) for backfills. Upstream fetches per day.

Items to ask Arnar:
- Does he enable All-Day Pulse Ox? Without it, SpO2 is sleep-only.
- Does he log food in Connect, and does he golf?
- Does he want a raw-JSON mirror of every response? It would capture unlisted fields.

Files and locations:
- Library source read: /tmp/claude-1000/-home-solmundur-Projects/7211be9d-d6b0-4eec-9a37-39bad1f7d3e0/scratchpad/coverage/.venv/lib/python3.13/site-packages/garminconnect/__init__.py and typed.py
- Upstream code read: /home/solmundur/Projects/garmin-surreal/src/garmin_grafana/garmin_fetch.py (FETCH_SELECTION line 62, get_daily_stats lines 212-287, get_sleep_data lines 316-500, dispatch lines 1642-1688)
- Repo not modified.