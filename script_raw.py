import time
import uiautomator2 as u2
from datetime import datetime, timedelta
import ntplib
import threading
import subprocess
import os
import signal

class AutomationApp:
    def __init__(self):
        self.device_ip = "device_ip"
        self.PIN_CODE = "password"
        #self.TARGET_APP = "com.teh.testapp"
        self.TARGET_APP = "com.ktb.customer.qr"
        self.TIME_OFFSET = 0.9
        self.BUY_TIME_AM = "07:30:00"
        self.BUY_TIME_PM = "15:00:00"
        self.DELAY_PIN = 0.03
        self.SWIPE_X1 = 0
        self.SWIPE_X2 = 0
        self.SWIPE_Y = 0
   
        self.device = None
        self.running = False
        self.sendActive = False
        self.buy_clicked = False
        self.buy_found = False
        self.onSwipe = False
        self.pin_clicked = False
        self.pin_login_attempted = False
        self.pin_glo_attempted = False

        self.swiped = False
        self.width = 0
        self.height = 0
        self.diff_ms = 0
        self.buy_time = None
        self.swipe_start = None

        self.BTN_L6 = "สลากหกหลัก"
        self.BTN_BUY = "ซื้อ-จอง ล่วงหน้า"
        self.BTN_CLOSE = "ปิด"
        self.BTN_OK1 = "ปุ่ม ตกลง"
        self.BTN_OK2 = "ตกลง"
        self.PIN_TEXT_TRIGGER = "ใส่รหัส PIN 6 หลัก"
        self.PIN_DELETE_TEXT = "ลบ"
        self.COMPLETED_TEXT = "ทำรายการจองสลาก สำเร็จ"
        self.COMPLETED_TEXT1 = "คุณจะได้รับผลการทำรายการ"
        self.COMPLETED_BUY_TEXT = "ทำรายการซื้อสลาก สำเร็จ"

    def connect_device(self):
        try:
            self.device = u2.connect(self.device_ip) # if self.device_id else u2.connect()
            print(f"✅ เชื่อมต่ออุปกรณ์สำเร็จ {self.device_ip}")
            self.send_status("connected")
            return True
        except Exception as e:
            print(f"❌ ไม่สามารถเชื่อมต่ออุปกรณ์: {e}")
            self.send_status(f"❌ ไม่สามารถเชื่อมต่ออุปกรณ์: {e}")
            return False

    def sync_ntp(self):
        max_retries = 20
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                client = ntplib.NTPClient()
                response = client.request('time.google.com', version=3, timeout=0.5)
                ntp_time = datetime.fromtimestamp(response.tx_time)
                self.diff_ms = (ntp_time - datetime.now()).total_seconds() * 1000
                print(f"🕒 NTP synced. Offset: {self.diff_ms:.2f} ms")
                return True
            except Exception as e:
                if attempt < max_retries - 1:  # Not the last attempt
                    print(f"⚠️ NTP sync ล้มเหลว (พยายามครั้งที่ {attempt + 1}): {e}")
                    time.sleep(retry_delay)
                else:  # Last attempt failed
                    print(f"⚠️ NTP sync ล้มเหลวหลังจากพยายาม {max_retries} ครั้ง: {e}")
                    self.diff_ms = 0
                    return False

    def get_adjusted_time(self):
        return datetime.now() + timedelta(milliseconds=self.diff_ms)

    def wait_until_ready(self):
        now = self.get_adjusted_time()
        buy_time_str = self.BUY_TIME_AM if now.time() < datetime.strptime("12:00:00", "%H:%M:%S").time() else self.BUY_TIME_PM
        buy_time_dt = datetime.combine(now.date(), datetime.strptime(buy_time_str, "%H:%M:%S").time())
        adjustment = timedelta(seconds=1.15 - self.TIME_OFFSET)
        self.buy_time = buy_time_dt - adjustment
        open_app_time = self.buy_time - timedelta(minutes=1, seconds=30) #เข้าก่อนเวลา 1 นาที 30 วินาที

        while self.get_adjusted_time() < open_app_time:
            current_time = self.get_adjusted_time()
            time_left = (open_app_time - current_time).total_seconds()
            hours, remainder = divmod(time_left, 3600)
            minutes, seconds = divmod(remainder, 60)

            try:
                message = (
                    f"⏳ รอเวลาเปิดแอพ...\n"
                    f"เหลืออีก {int(hours)} ชั่วโมง {int(minutes)} นาที {int(seconds)} วินาที"
                )
                print(message)
                self.send_message(message)
            except Exception as e:
                print(e)
            time.sleep(1)
        return True

    def verify_adb_enabled(self):
        try:
            adb_enabled = self.device.shell('settings get global adb_enabled').output.strip()
            adb_wifi_enabled = self.device.shell('settings get global adb_wifi_enabled').output.strip()
            if adb_enabled == '2' or adb_wifi_enabled == '2':
                return True
            if adb_enabled != '2':
                print(f"❌ Hook USB ไม่สำเร็จ (ได้ค่า: {adb_enabled}, ต้องการ: 2)")
                self.send_status("ADB USB ไม่ถูกต้อง")
            if adb_wifi_enabled != '2':
                print(f"❌ Hook WiFi ไม่สำเร็จ (ได้ค่า: {adb_wifi_enabled}, ต้องการ: 2)")
                self.send_status("ADB WiFi ไม่ถูกต้อง")
            return False

        except Exception as e:
            error_msg = f"เกิดข้อผิดพลาดขณะตรวจสอบ ADB: {str(e)}"
            print(f"❌ {error_msg}")
            self.send_status(error_msg)
            return False

    def do_hook(self):
        try:
            self.device.shell('settings put global adb_enabled 2')
            time.sleep(0.5)
            self.device.shell('settings put global adb_wifi_enabled 2')
            time.sleep(0.5)

            if self.verify_adb_enabled():
                print("🎉 Hook ADB สำเร็จทั้ง USB และ WiFi")
                return True
            else:
                print("⚠️ Hook ADB ไม่สำเร็จ กรุณาตรวจสอบการตั้งค่า")
                return False

        except Exception as e:
            error_msg = f"Hook Error: {str(e)}"
            print(f"❌ {error_msg}")
            self.send_status(error_msg)
            return False

    def send_broadcast(self, key, value):
        try:
            subprocess.run([
                'am', 'broadcast',
                '-a', 'com.teh.tlotto_cm.ACTION_SCRIPT_UPDATE',
                f'--es', key, value,
                '-n', 'com.teh.tlotto_cm/.ScriptUpdateReceiver'
            ], check=True)
        except Exception as e:
            print(f"❌ ส่ง broadcast ล้มเหลว: {e}")

    def send_status(self, msg):
        self.send_broadcast('status', msg)

    def send_message(self, msg):
        self.send_broadcast('waiting', msg)

    def send_logcat(self, msg):
        print("logcat")
        #self.send_broadcast('logcat', msg)

    def complete_monitor(self):
        while self.running:
            if self.device(textContains=self.COMPLETED_TEXT).exists or self.device(textContains=self.COMPLETED_TEXT1).exists or self.device(text=self.COMPLETED_BUY_TEXT).exists:
                print("✅ ทำรายการสำเร็จ")
                self.send_status("success")
                self.running = False
                print("🛑 หยุด Termux session...")
                os.kill(os.getpid(), signal.SIGKILL)
                return
            elif self.swipe_start is not None and (self.get_adjusted_time() - self.swipe_start).total_seconds() > 60:
                self.send_status("หยุดทำงานแล้ว")
                self.running = False
                os.kill(os.getpid(), signal.SIGKILL)
                return
            time.sleep(0.2)


    def click_close_button(self, label):
        while self.running:
            if self.device(text=label).exists:
                self.device(text=label).click()
            time.sleep(2)

    def click_ok_button(self, label):
        while self.running:
            if self.device(text=label).exists:
                self.device(text=label).click()
                self.buy_clicked = False
            elif self.device(description=label).exists:
                self.device(description=label).click()
                self.buy_clicked = False   
            time.sleep(1)

    def enter_pin(self):
        time.sleep(0.1)
        coords = {}
        for digit in set(self.PIN_CODE):
            if not self.device(text=digit).exists():
                return False
            coords[digit] = self.device(text=digit).info['bounds']

        for digit in self.PIN_CODE:
            b = coords[digit]
            x = (b['left'] + b['right']) // 2
            y = (b['top'] + b['bottom']) // 2
            self.device.click(x, y)
            time.sleep(self.DELAY_PIN)
        return True

    def swipe_if_pin_hidden(self):
        if not self.device(text=self.PIN_TEXT_TRIGGER).exists and not self.swiped:
            y = self.SWIPE_Y
            start_x = self.SWIPE_X1
            end_x = self.SWIPE_X2
            self.device.swipe(start_x, y, end_x, y, 0.02)
            self.send_logcat("🔄 Swipe submit")
            time.sleep(0.025)

    def click_buy_and_pin(self):
        last_print = self.get_adjusted_time()

        while self.running and (not (self.buy_clicked and self.pin_clicked)):
            try:
                if not self.buy_clicked and self.device(text=self.BTN_BUY).exists():
                    btn_bounds = self.device(text=self.BTN_BUY).info.get('bounds')
                    btn_prepared = False
                    if btn_bounds and not self.onSwipe:
                        center_x = (btn_bounds['left'] + btn_bounds['right']) // 2
                        center_y = (btn_bounds['top'] + btn_bounds['bottom']) // 2
                        print(f"{center_x}, {center_y}")

                        if self.buy_time > self.get_adjusted_time():
                            while True:
                                now = self.get_adjusted_time()
                                diff = (self.buy_time - now).total_seconds()
                                print(f"เหลือ {diff:.1f} วินาที")

                                if diff <= 30 and not btn_prepared:
                                    btn_bounds = self.device(text=self.BTN_BUY).info.get('bounds', None)
                                    center_x = (btn_bounds['left'] + btn_bounds['right']) // 2
                                    center_y = (btn_bounds['top'] + btn_bounds['bottom']) // 2
                                    btn_prepared = True
                                    print(f" diff < 30 {center_x}, {center_y}")

                                if diff <= 0.5:
                                    break

                                if (now - last_print).total_seconds() >= 5 and diff > 5:
                                    ySwipe = self.height * 0.45
                                    self.device.swipe(20, ySwipe, 20, ySwipe + 70, 0.1)
                                    print("🔄 Swipe")
                                    last_print = now

                                time.sleep(0.2 if diff <= 2 else 1)

                            while self.get_adjusted_time() < self.buy_time:
                                time.sleep(0.001)

                        self.device.click(center_x, center_y)
                        time.sleep(1)
                        self.buy_clicked = True
                        self.swipe_start = self.get_adjusted_time()

                elif self.buy_clicked and not self.pin_clicked:
                    diff_swipe = (self.get_adjusted_time() - self.swipe_start).total_seconds()
                    if diff_swipe < 10:
                        self.swipe_if_pin_hidden()
                    if self.device(text=self.PIN_TEXT_TRIGGER).exists() and not self.pin_glo_attempted:
                        self.swiped = True
                        if self.enter_pin():
                            self.pin_clicked = True
                            self.pin_glo_attempted = True
                            print(f"🔐 PIN GLO")
                else:
                    if self.device(text=self.PIN_TEXT_TRIGGER).exists() and not self.pin_login_attempted:
                        time.sleep(2)
                        if self.enter_pin():
                            self.pin_login_attempted = True
                            print(f"🔐 PIN LOGIN")

            except Exception as e:
                print(f"⚠️ click_buy_and_pin error: {e}")
            time.sleep(0.1)

    def click_l6_and_swipe(self):
        try:
            while self.running and not self.buy_found:
                try:
                    if self.device(text=self.BTN_L6).exists:
                        self.device(text=self.BTN_L6).click()
                        print("🖱️ Clicked BTN_L6")
                        time.sleep(4)
                        self.buy_found = False

                        while self.running and not self.buy_found:
                            if self.device(text=self.BTN_BUY).exists:
                                self.buy_found = True
                            else:
                                self.onSwipe = True
                                self.device.swipe(20, 500, 20, 2000, 0.1)
                                time.sleep(4)
                                self.onSwipe = False

                except Exception:
                    pass
                time.sleep(0.1)
        except Exception:
            pass

    def start_threads(self):
        self.width, self.height = self.device.window_size()
        print(f"📱 ขนาดหน้าจอ: {self.width}x{self.height}")

        threads = [
            threading.Thread(target=self.click_ok_button, args=(self.BTN_OK1,)),
            threading.Thread(target=self.click_ok_button, args=(self.BTN_OK2,)),
            threading.Thread(target=self.click_close_button, args=(self.BTN_CLOSE,)),
            threading.Thread(target=self.click_l6_and_swipe),
            threading.Thread(target=self.click_buy_and_pin),
            threading.Thread(target=self.complete_monitor)
        ]
        for t in threads:
            t.daemon = True
            t.start()

    def main(self):
        self.send_status("loaded")
        if not self.connect_device():
            self.send_status("connect_device_failed")
            return
        if not self.sync_ntp():
            self.send_status("ntp_sync_failed")
            return
        if not self.do_hook():
            self.send_status("do_hook_failed")
            return
        if not self.wait_until_ready():
            self.send_status("wait_until_ready_failed")
            return
        self.running = True
        self.send_status("running")
        if not self.sendActive:
            self.send_status("active")
            self.sendActive = True
            print(self.send_status("active"))
        self.device.app_start(self.TARGET_APP)
        self.start_threads()
        while self.running:
            time.sleep(0.1)

if __name__ == "__main__":
    app = AutomationApp()
    app.main()