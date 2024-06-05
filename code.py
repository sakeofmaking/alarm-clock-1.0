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
from adafruit_datetime import datetime, timedelta
import rtc


# Initialize variables
pool = socketpool.SocketPool(wifi.radio)
ntp_server = 'time1.google.com'
ntp = adafruit_ntp.NTP(pool, server=ntp_server, tz_offset=0)
now = ''
scan_count = 0
total_seconds = 0
noon_seconds = 43200  # Seconds from midnight to noon
midnight_seconds = 86400  # Seconds from midnight to midnight
utc_offset = 8  # Hours from UTC to PST
daylight_saving = True
wifi_flag = False
alarm_time = '0530'  # Time alarm triggers. Yes, I really wake up that early everyday
alarm_active = False
alarm_duration_sec = 300
button_pressed = False

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
        return False

# Pings Google
def ping_google_test():
    ipv4 = ipaddress.ip_address('8.8.4.4')
    print("Ping google.com: %f ms" % (wifi.radio.ping(ipv4)*1000))

# Return seconds from midnight
def seconds_from_midnight(struct_time, daylight_flag, offset):
    if daylight_flag:  # Adjust for UTC and Daylight
        hours = struct_time.tm_hour - offset + 1
    else:
        hours = struct_time.tm_hour - offset
    if hours < 0:
        hours = hours + 24
    minutes = struct_time.tm_min
    seconds = struct_time.tm_sec
    return hours * 3600 + minutes * 60 + seconds

# Display the time
def display_time(time_in_seconds):
    global display
    hours_display = time_in_seconds // 3600
    minutes_display = (time_in_seconds - (hours_display * 3600)) // 60
    # seconds_display = time_in_seconds - (hours_display * 3600) - (minutes_display * 60)
    time_display = f"{hours_display:02d}:{minutes_display:02d}"
    display.print(time_display)

# Is Daylight
def is_daylight(struct_time):
    # Catch 22, today's date is dependent on whether it's Daylight Saving or not ¯\_(ツ)_/¯
    todays_date = datetime(struct_time.tm_year, struct_time.tm_mon, struct_time.tm_mday)
    year = todays_date.year

    # Calculate the second Sunday in March
    march_start = datetime(year, 3, 1)
    march_start_day_of_week = march_start.weekday()  # Monday is 0, Sunday is 6
    second_sunday_march = march_start + timedelta(days=(6 - march_start_day_of_week + 7))
    
    # Calculate the first Sunday in November
    november_start = datetime(year, 11, 1)
    november_start_day_of_week = november_start.weekday()  # Monday is 0, Sunday is 6
    first_sunday_november = november_start + timedelta(days=(6 - november_start_day_of_week))
    
    # Check if the todays_date is within the DST period
    return second_sunday_march <= todays_date < first_sunday_november

# NTP Sync
def ntp_sync(network_flag):
    global ntp, ntp_server
    if network_flag:
        my_rtc.datetime = ntp.datetime  # Set RTC to NTP time
        print(f'Synced with NTP server ({ntp_server})')
        return my_rtc.datetime
    else:
        # Todo: Setup manual way to set time via rotary encoder
        pass

# Alarm Seconds from Midnight
def alarm_sec_from_midnight(alarm_time_str):
    alarm_hour = int(alarm_time_str[0:2])
    alarm_minute = int(alarm_time_str[2:4])
    return alarm_hour * 3600 + alarm_minute * 60


# Setup
wifi_flag = connect_to_wifi()  # Connect to wifi
now = ntp_sync(wifi_flag)  # Sync time with NTP server
daylight_saving = is_daylight(now)
total_seconds = seconds_from_midnight(now, daylight_saving, utc_offset)
display_time(total_seconds)
alarm_seconds = alarm_sec_from_midnight(alarm_time)

# Main Loop
while True:
    scan_count = scan_count + 1  # Increment scan count

    if scan_count % 94 == 0:  # 1 second has passed
        total_seconds = total_seconds + 1  # Increment total seconds

    # Update total_seconds
    if total_seconds == noon_seconds:
        now = ntp_sync(wifi_flag)  # Sync time with NTP server
        total_seconds = seconds_from_midnight(now, daylight_saving, utc_offset)
    elif total_seconds == midnight_seconds:
        total_seconds = 0
        scan_count = 0

    # Check Alarm
    if total_seconds == alarm_seconds:
        alarm_active = True
    elif (total_seconds >= (alarm_seconds + alarm_duration_sec)) or button_pressed:
        alarm_active = False
    
    # Update Alarm
    if alarm_active:
        # Trigger alarm
        display.blink_rate = 2
        button_pressed = button.value  # Check button status
        if (scan_count % 50 == 0):
            button_led.value = not button_led.value  # Toggle button led
            buzzer.value = not buzzer.value  # Toggle buzzer
    else:
        # Disable alarm
        display.blink_rate = 0
        button_led.value = False
        buzzer.value = False
        button_pressed = False
    
    # Update display
    if total_seconds % 60 == 0:  # 1 minute has passed
        display_time(total_seconds)

    time.sleep(0.01)


