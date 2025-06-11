import time
import uiautomator2 as u2
from datetime import datetime, timedelta
import ntplib
import threading
import subprocess

# === ตั้งค่าเริ่มต้น ===
DEVICE_ID = "192.168.1.10:5555"  # เปลี่ยนเป็น IP ของอุปกรณ์
PIN_CODE = "899999"
TARGET_APP = "com.teh.testapp"
#TARGET_APP = "com.ktb.customer.qr"
BUY_TIME = "15:00:00"
BTN_L6 = "สลากหกหลัก"
BTN_BUY = "ซื้อ-จอง ล่วงหน้า"
BTN_CLOSE = "ปิด"
BTN_OK1 = "ปุ่ม ตกลง"
BTN_OK2 = "ตกลง"
PIN_TEXT_TRIGGER = "ใส่รหัส PIN 6 หลัก"
PIN_DELETE_TEXT = "ตกลง"
COMPLETED_TEXT = "ทำรายการจองสลาก สำเร็จ"
COMPLETED_BUY_TEXT = "ทำรายการซื้อสลาก สำเร็จ"
DELAY_PIN = 0.03
SWIPE_HEIGHT = 2060  # ความสูงของหน้าจอที่ใช้ในการปัด
SWIPE_WIDTH_RATIO = 0.1
TIME_OFFSET = 0.9

running = False
width = 0
height = 0
diff_ms = 0
clicked = False
buy_clicked = False

def init_ntp_sync():
    global diff_ms
    start_time = time.time()
    attempts = 0
    
    while time.time() - start_time < 3:  # พยายามนาน 3 วินาที
        try:
            attempts += 1
            client = ntplib.NTPClient()
            response = client.request('time.google.com', version=3, timeout=0.5)
            ntp_time = datetime.fromtimestamp(response.tx_time)
            local_time = datetime.now()
            diff_ms = (ntp_time - local_time).total_seconds() * 1000
            return True
        except Exception as e:
            print(f"❌ พยายามครั้งที่ {attempts} ล้มเหลว: {str(e)[:50]}...")
            time.sleep(0.1)  # รอ 0.1 วินาทีก่อนลองใหม่
    
    print("⚠️ ไม่สามารถเชื่อมต่อ NTP ได้ภายใน 3 วินาที ใช้เวลาเครื่องแทน")
    diff_ms = 0
    return False

def get_adjusted_time():
    """คืนค่าเวลาปัจจุบัน (เวลาเครื่อง + diff_ms)"""
    return datetime.now() + timedelta(milliseconds=diff_ms)

def wait_until():
    global running, buy_time

    now = get_adjusted_time()
    if now.time() < datetime.strptime("12:00:00", "%H:%M:%S").time():
        BUY_TIME = "07:30:00"
    else:
        BUY_TIME = "15:00:00"

    buy_time_set = datetime.strptime(BUY_TIME, "%H:%M:%S").time()
    now = get_adjusted_time()
    buy_datetime = datetime.combine(now.date(), buy_time_set)
    adjustment_seconds = 1.15 - TIME_OFFSET
    buy_time = buy_datetime - timedelta(seconds=adjustment_seconds)
    open_app_time = buy_time - timedelta(minutes=3)
    today = get_adjusted_time().date()
    open_app_dt = datetime.combine(today, open_app_time.time())

    running = False
    while not running:
        current_time = get_adjusted_time()
        if current_time >= open_app_dt:
            running = True
            return True

        time_left = (open_app_dt - current_time).total_seconds()

        # Calculate hours, minutes, seconds
        hours, remainder = divmod(time_left, 3600)
        minutes, seconds = divmod(remainder, 60)

        # First print format
        print(f"⏳ รอถึงเวลาเปิดแอพ... เหลืออีก {time_left:.2f} วินาที")

        # Second message format
        message = (
            f"⏳ รอเวลาเปิดแอพ...\n"
            f"เหลืออีก {int(hours)} ชั่วโมง {int(minutes)} นาที {int(seconds)} วินาที"
        )

        print(message)
        send_running(message)

        time.sleep(0.5)

    return True


def verify_adb_enabled(d):
    try:
        adb_enabled = d.shell('settings get global adb_enabled').output.strip()
        adb_wifi_enabled = d.shell('settings get global adb_wifi_enabled').output.strip()
        return adb_enabled == '2' and adb_wifi_enabled == '2'
    except Exception as e:
        print(f"❌ ตรวจสอบ ADB ไม่สำเร็จ: {e}")
        send_error(f"❌ ตรวจสอบ ADB ไม่สำเร็จ: {e}")
        return False

def do_hook(d):
    try:
        d.shell('settings put global adb_enabled 2')
        d.shell('settings put global adb_wifi_enabled 2')
        if verify_adb_enabled(d):
            print("🔗 Hook ADB เรียบร้อย")
        else:
            print("❌ Hook ADB ไม่สำเร็จ")
    except Exception as e:
        print(f"❌ Hook Error: {e}")

def send_success():
    subprocess.run([
        'am', 'broadcast',
        '-a', 'com.teh.tlotto_cm.ACTION_SCRIPT_UPDATE',
        '--es', 'status', 'success',
        '-n', 'com.teh.tlotto_cm/.ScriptUpdateReceiver'
    ])
def send_script_loaded():
    subprocess.run([
        'am', 'broadcast',
        '-a', 'com.teh.tlotto_cm.ACTION_SCRIPT_UPDATE',
        '--es', 'status', 'loaded',
        '-n', 'com.teh.tlotto_cm/.ScriptUpdateReceiver'
    ])
def send_running(msg):
    subprocess.run([
        'am', 'broadcast',
        '-a', 'com.teh.tlotto_cm.ACTION_SCRIPT_UPDATE',
        '--es', 'message', msg,
        '-n', 'com.teh.tlotto_cm/.ScriptUpdateReceiver'
    ])

def send_error(msg):
    subprocess.run([
        'am', 'broadcast',
        '-a', 'com.teh.tlotto_cm.ACTION_SCRIPT_UPDATE',
        '--es', 'status', msg,
        '-n', 'com.teh.tlotto_cm/.ScriptUpdateReceiver'
    ])

def complete(d):
    global running
    while running:
        if d(text=COMPLETED_TEXT).exists or d(text=COMPLETED_BUY_TEXT).exists:
            print("✅ สำเร็จ")
            send_success()  # ส่งแค่สถานะ success
            running = False
            return
        time.sleep(0.2)

def click_ok(d):
    global buy_clicked
    while running:
        if d(text=BTN_OK1).exists:
            d(text=BTN_OK1).click()
            buy_clicked = False
            return buy_clicked
        elif d(text=BTN_OK2).exists:
            d(text=BTN_OK2).click()
            buy_clicked = False
            return buy_clicked
        time.sleep(0.1)

def click_L6(d):
    global clicked

    while running and not clicked:
        if d(text=BTN_L6).exists:
            d(text=BTN_L6).click()
            time.sleep(2)
            found = False
            while found:
                if d(text=BTN_BUY).exists:
                    clicked = True
                    found = True
                    print("🟦 คลิกปุ่ม L6 แล้ว")
                else:
                    d.swipe(20, 500, 20, 2000, 0.1)
            time.sleep(3)
            break
        time.sleep(1)

def click_close(d):
    while running:
        if d(text=BTN_CLOSE).exists:
            d(text=BTN_CLOSE).click()
        time.sleep(0.1)


def click_buy_and_pin(d, buy_time, width, height):
    try:
        pin_coordinates = {}
        global buy_clicked
        pin_clicked = False
        on_swipe = False
        last_print_time = get_adjusted_time()

        def enter_pin():
            nonlocal pin_coordinates, pin_clicked
            if not PIN_CODE or len(PIN_CODE) != 6:
                return False

            # หาตำแหน่งปุ่ม PIN ถ้ายังไม่มีใน pin_coordinates
            for digit in PIN_CODE:
                if digit not in pin_coordinates:
                    if d(text=digit).exists:
                        pin_coordinates[digit] = d(text=digit).info['bounds']
                    else:
                        return False

            # คลิกปุ่ม PIN ตามลำดับ
            for digit in PIN_CODE:
                bounds = pin_coordinates[digit]
                d.click(
                    bounds['left'] + (bounds['right'] - bounds['left']) / 2,
                    bounds['top'] + (bounds['bottom'] - bounds['top']) / 2
                )
                #time.sleep(DELAY_PIN)

            print("🔐 ใส่ PIN เรียบร้อย")
            pin_coordinates = {}
            time.sleep(3)

            # ตรวจสอบและลบ PIN หากยังมีข้อความแสดงอยู่
            if d(text=PIN_DELETE_TEXT).exists:
                print("⚠️ พบข้อความเกี่ยวกับการเข้าสู่ระบบ กำลังลบ PIN")
                for i in range(5):
                    if d(text=PIN_DELETE_TEXT).exists:
                        d(text=PIN_DELETE_TEXT).click()
                        print(f"ลบ PIN คลิก ({i+1})")
                        time.sleep(0.1)
                    else:
                        break
            return True

        while not (buy_clicked and pin_clicked):
            try:
                # เรียกใช้ click_ok เพื่อตรวจสอบปุ่ม OK
                if d(text=BTN_OK1).exists or d(text=BTN_OK2).exists:
                    click_ok(d)  # จะส่งค่า False กลับมาและอัพเดต buy_clicked เมื่อคลิกปุ่ม OK

                # ส่วนการคลิกปุ่มซื้อ
                if not buy_clicked and d(text=BTN_BUY).exists:
                    btn_bounds = d(text=BTN_BUY).info.get('bounds', None)
                    btn_prepared = False

                    if btn_bounds and not on_swipe:
                        center_x = (btn_bounds['left'] + btn_bounds['right']) // 2
                        center_y = (btn_bounds['top'] + btn_bounds['bottom']) // 2
                        print(f"📍 ตำแหน่งปุ่มซื้อ: {center_x}, {center_y}")

                        if buy_time > get_adjusted_time():
                            while True:
                                now = get_adjusted_time()
                                diff = (buy_time - now).total_seconds()
                                print(f"⏳ เวลาที่เหลือก่อนซื้อ: {diff:.1f} วินาที")

                                # เตรียมพร้อมเมื่อเหลือเวลา 30 วินาที
                                if diff <= 30 and not btn_prepared:
                                    btn_bounds = d(text=BTN_BUY).info.get('bounds', None)
                                    if btn_bounds:
                                        center_x = (btn_bounds['left'] + btn_bounds['right']) // 2
                                        center_y = (btn_bounds['top'] + btn_bounds['bottom']) // 2
                                        btn_prepared = True
                                        print(f"⏳ เตรียมพร้อมคลิก (เหลือเวลา {diff:.1f} วินาที): {center_x}, {center_y}")

                                if diff <= 0.5:
                                    break

                                # ปัดหน้าจอทุก 10 วินาทีเพื่อป้องกันหน้าจอล็อก
                                if (now - last_print_time).total_seconds() >= 5 and diff > 10:
                                    y_swipe = height * 0.45
                                    d.swipe(20, y_swipe, 20, y_swipe + 70, 0.1)
                                    last_print_time = now
                                    print("🔄 ปัดหน้าจอเพื่อป้องกันล็อก")

                                time.sleep(0.2 if diff <= 2 else 1)

                            # รอจนถึงเวลาที่กำหนด
                            while get_adjusted_time() < buy_time:
                                time.sleep(0.001)

                            print(f"🟢 คลิกปุ่มซื้อที่เวลา: {get_adjusted_time()}")
                            d.click(center_x, center_y)
                            buy_clicked = True
                            print(f"✅ คลิกสำเร็จที่เวลา: {get_adjusted_time()}")

                        else:
                            print("⚠️ เกินเวลาที่กำหนดแล้ว")
                            d.click(center_x, center_y)
                            buy_clicked = True
                            print(f"🕒 คลิกเกินเวลา: {get_adjusted_time()}")

                # ส่วนการใส่ PIN หลังจากคลิกซื้อแล้ว
                elif buy_clicked and not pin_clicked:
                    if not d(text=PIN_TEXT_TRIGGER).exists():
                        y = SWIPE_HEIGHT
                        start_x = width * SWIPE_WIDTH_RATIO
                        end_x = width - 10
                        d.swipe(start_x, y, end_x, y, 0.02)
                        on_swipe = True
                        print("🔄 ปัดหน้าจอเพื่อแสดงปุ่ม PIN")
                    else:
                        if enter_pin():
                            pin_clicked = True
                            print("✅ ใส่ PIN สำเร็จ")
                else:
                    if d(text=PIN_TEXT_TRIGGER).exists():
                        enter_pin()

            except Exception as e:
                print(f"❌ เกิดข้อผิดพลาดในกระบวนการซื้อ/PIN: {e}")

            time.sleep(0.1)

    except Exception as e:
        print(f"❌ ข้อผิดพลาดร้ายแรงใน click_buy_and_pin: {e}")

def main():
    global running, width, height
    send_script_loaded()
    print(f"🔌 เชื่อมต่ออุปกรณ์: {DEVICE_ID}")
    try:
        d = u2.connect(DEVICE_ID)  # ใช้การเชื่อมต่อกับอุปกรณ์ที่ระบุ
        # d = u2.connect()  # หรือใช้แบบนี้ถ้าต้องการเชื่อมกับอุปกรณ์ที่เชื่อมอยู่แล้ว
    except Exception as e:
        print(f"❌ ไม่สามารถเชื่อมต่อ: {e}")
        send_error(f"❌ ไม่สามารถเชื่อมต่อ: {e}" )
        return

    do_hook(d)

    if init_ntp_sync() and wait_until():
        running = True
        print("🚀 กำลังเปิดแอป...")

        d.app_start(TARGET_APP)
        
        # รับขนาดหน้าจอ
        width, height = d.window_size()
        print(f"📱 ขนาดหน้าจอ: {width}x{height}")

        # สร้างและเริ่ม threads
        threads = [
            threading.Thread(target=click_L6, args=(d,), name="Thread-ClickL6"),
            threading.Thread(target=click_ok, args=(d,), name="Thread-ClickOK"),
            threading.Thread(target=click_close, args=(d,), name="Thread-ClickClose"),
            threading.Thread(target=click_buy_and_pin, args=(d, buy_time, width, height), name="Thread-BuyAndPin"),
            threading.Thread(target=complete, args=(d,), name="Thread-Complete")
        ]

        for thread in threads:
            thread.daemon = True
            thread.start()

        while running:
            time.sleep(0.1)

if __name__ == "__main__":
    main()