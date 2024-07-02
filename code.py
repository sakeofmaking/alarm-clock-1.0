# V1.0


import os
import ipaddress
import wifi
import socketpool
import time
import adafruit_ntp
import board
import digitalio
import busio
from adafruit_ht16k33.segments import Seg7x4
from adafruit_datetime import datetime as dt_datetime, timedelta as dt_timedelta
import rtc


# Initialize variables
pool = socketpool.SocketPool(wifi.radio)
ntp_server = 'time1.google.com'
ntp = adafruit_ntp.NTP(pool, server=ntp_server, tz_offset=0)
cycle_count = 0
noon_time_secs = 43200
midnight_time_secs = 0
pst_offset = 8  # Hours from UTC to PST
daylight_saving = True
wifi_flag = False
alarm_time_secs = 19800  # Time alarm triggers in seconds. Yes, I really wake up that early every morning
alarm_duration_secs = 300  # Seconds
alarm_active = False

# Initialize display
i2c = busio.I2C(scl=board.GP5, sda=board.GP4)
display = Seg7x4(i2c)
display.brightness = 0.5
display.blink_rate = 0

# Initialize IO
button = digitalio.DigitalInOut(board.GP9)
button.switch_to_input(pull=digitalio.Pull.DOWN)
button_led = digitalio.DigitalInOut(board.GP10)
button_led.direction = digitalio.Direction.OUTPUT
buzzer = digitalio.DigitalInOut(board.GP2)
buzzer.direction = digitalio.Direction.OUTPUT

# Initialize RTC
my_rtc = rtc.RTC()


# Connect to Wifi
def connect_to_wifi():
    print('Connecting to WiFi')
    try:
        wifi.radio.connect(os.getenv('CIRCUITPY_WIFI_SSID'), os.getenv('CIRCUITPY_WIFI_PASSWORD'))
        print('Connected to WiFi')
        return True
    except Exception as e:
        print(f'Failed to connect to Wifi: {e}')
        print('Waiting 5 seconds before trying again...')
        time.sleep(5)
        return False

# Pings Google
def ping_google_test():
    ipv4 = ipaddress.ip_address('8.8.4.4')
    print("Ping google.com: %f ms" % (wifi.radio.ping(ipv4)*1000))

# Display the time
def update_display(struct_time):
    global display
    time_display = f"{struct_time.tm_hour:02d}:{struct_time.tm_min:02d}"
    display.print(time_display)

# Is Daylight
def is_daylight(struct_time):
    # Catch 22, today's date is dependent on whether it's Daylight Saving or not ¯\_(ツ)_/¯
    todays_date = dt_datetime(struct_time.tm_year, struct_time.tm_mon, struct_time.tm_mday)
    year = todays_date.year

    # Calculate the second Sunday in March
    march_start = dt_datetime(year, 3, 1)
    march_start_day_of_week = march_start.weekday()  # Monday is 0, Sunday is 6
    second_sunday_march = march_start + dt_timedelta(days=(6 - march_start_day_of_week + 7))
    
    # Calculate the first Sunday in November
    november_start = dt_datetime(year, 11, 1)
    november_start_day_of_week = november_start.weekday()  # Monday is 0, Sunday is 6
    first_sunday_november = november_start + dt_timedelta(days=(6 - november_start_day_of_week))
    
    # Check if the todays_date is within the DST period
    return second_sunday_march <= todays_date < first_sunday_november

# NTP Sync
def ntp_sync():
    global my_rtc, ntp, ntp_server

    # Sync with NTP server
    utc_struct_time = ntp.datetime
    print(f'Synced with NTP server ({ntp_server})')

    # Adjust for Daylight Saving
    daylight_saving = is_daylight(utc_struct_time)
    adjusted_struct_time = adjust_for_pst_and_ds(utc_struct_time, pst_offset, daylight_saving)

    # Set RTC to adjusted time
    my_rtc.datetime = adjusted_struct_time

# Adjust for PST and Daylight Saving
def adjust_for_pst_and_ds(struct_time, offset, flag):
    # Convert struct_time to datetime
    todays_date = dt_datetime(struct_time.tm_year, struct_time.tm_mon, struct_time.tm_mday, struct_time.tm_hour, struct_time.tm_min, struct_time.tm_sec)

    # Adjust hour according to Daylight Saving
    if flag:
        adjusted_datetime = todays_date - dt_timedelta(hours=(offset - 1))
    else:
        adjusted_datetime = todays_date - dt_timedelta(hours=offset)

    # Convert datetime to struct_time
    return adjusted_datetime.timetuple()

# Struct Time to Seconds
def struct_to_sec(struct_time):
    hours = struct_time.tm_hour
    minutes = struct_time.tm_min
    seconds = struct_time.tm_sec
    return hours * 3600 + minutes * 60 + seconds

# Setup
while not wifi_flag:
    wifi_flag = connect_to_wifi()  # Connect to wifi
ntp_sync()  # Sync RTC with NTP server and adjust for PST and Daylight Saving
update_display(my_rtc.datetime)

# Main Loop
while True:
    cycle_count = cycle_count + 1  # Increment scan count

    # Each Second
    if cycle_count % 100 == 0:
        # Update Alarm
        if alarm_active:
            # Trigger Alarm
            display.blink_rate = 2  # Flash LED display
            button_led.value = not button_led.value  # Toggle button led
            buzzer.value = not buzzer.value  # Toggle buzzer
        else:
            # Disable Alarm
            display.blink_rate = 0
            button_led.value = False
            buzzer.value = False
        
        # Update RTC
        if struct_to_sec(my_rtc.datetime) == noon_time_secs:
            while not wifi_flag:
                wifi_flag = connect_to_wifi()  # Connect to wifi
            ntp_sync()  # Sync RTC with NTP server and adjust for PST and Daylight Saving

        # Reset Cycle Count
        if struct_to_sec(my_rtc.datetime) == midnight_time_secs:
            cycle_count = 0

        # Update Display
        update_display(my_rtc.datetime)

    # Check Alarm
    if struct_to_sec(my_rtc.datetime) == alarm_time_secs:
        alarm_active = True
    elif (struct_to_sec(my_rtc.datetime) >= (alarm_time_secs + alarm_duration_secs)) or button.value:
        alarm_active = False

    time.sleep(0.01)
