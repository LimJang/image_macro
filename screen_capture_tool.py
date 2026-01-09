import tkinter as tk
from tkinter import Toplevel, Canvas, Button, Label, simpledialog
from PIL import Image, ImageTk
import mss
import os
import time

import tkinter as tk
from tkinter import Toplevel, Canvas, Button, Label, simpledialog
from PIL import Image, ImageTk
import mss.tools
import os
import time
import subprocess # subprocess 추가

class ScreenCaptureTool:
    def __init__(self, master, on_image_selected):
        self.master = master
        self.on_image_selected = on_image_selected
        
        # [중요] 절대 경로 설정
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.temp_screenshot_path = os.path.join(self.base_dir, "temp_screenshot.png")
        
        self.selection_window = None
        self.start_x = self.start_y = 0
        self.current_x = self.current_y = 0
        self.rect_id = None
        self.original_image = None
        self.tk_image = None # Keep a reference to avoid garbage collection

    def capture_and_select(self):
        try:
            # macOS 기본 스크린샷 명령어 사용 (안정성 확보)
            # -x: 소리 없음, -m: 메인 모니터만(필요시) - 지금은 전체 캡처를 위해 옵션 최소화
            # 전체 화면 캡처: screencapture -x 파일경로
            print(f"DEBUG: macOS screencapture 명령어로 캡처 시도... 저장 경로: {self.temp_screenshot_path}")
            subprocess.run(["screencapture", "-x", self.temp_screenshot_path], check=True)
            
            # 파일이 실제로 생성되었는지 확인
            if not os.path.exists(self.temp_screenshot_path):
                 raise Exception("스크린샷 파일이 생성되지 않았습니다.")

            self.original_image = Image.open(self.temp_screenshot_path)
            self._show_selection_window()
            
        except Exception as e:
            print(f"!!! 에러 발생 (Screen Capture Tool) !!!: {e}")
            import traceback
            traceback.print_exc()
            # 에러 발생 시 메인 윈도우를 다시 복구해야 함
            if self.master:
                self.master.deiconify()
            
        except Exception as e:
            print(f"!!! 에러 발생 (Screen Capture Tool) !!!: {e}")
            import traceback
            traceback.print_exc()
            # 에러 발생 시 메인 윈도우를 다시 복구해야 함
            if self.master:
                self.master.deiconify()

    def _show_selection_window(self):
        print("DEBUG: 캡처된 이미지 로딩 및 선택 창 표시 시작")
        self.selection_window = Toplevel(self.master)
        
        # 화면의 논리 해상도 가져오기
        screen_width = self.selection_window.winfo_screenwidth()
        screen_height = self.selection_window.winfo_screenheight()
        
        self.selection_window.geometry(f"{screen_width}x{screen_height}+0+0")
        self.selection_window.attributes("-topmost", True)
        self.selection_window.title("영역 선택")

        # Esc 키로 종료
        self.selection_window.bind("<Escape>", self._close_selection_window)

        try:
            # 캡처된 이미지 불러오기 (원본)
            self.original_image = Image.open(self.temp_screenshot_path)
            orig_w, orig_h = self.original_image.size
            print(f"DEBUG: 원본 이미지 크기: {orig_w}x{orig_h}, 화면 크기: {screen_width}x{screen_height}")

            # 비율 계산 (원본 / 화면)
            # 보통 Retina에서는 원본이 화면보다 2배 큼
            self.scale_x = orig_w / screen_width
            self.scale_y = orig_h / screen_height
            
            # 화면에 맞게 리사이즈 (보여주기용)
            resized_image = self.original_image.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
            self.tk_image = ImageTk.PhotoImage(resized_image)
            
            self.canvas = Canvas(self.selection_window, cursor="cross", width=screen_width, height=screen_height)
            self.canvas.pack(fill=tk.BOTH, expand=tk.YES)
            self.canvas.create_image(0, 0, image=self.tk_image, anchor=tk.NW)
            
            self.canvas.bind("<ButtonPress-1>", self._on_button_press)
            self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
            self.canvas.bind("<ButtonRelease-1>", self._on_button_release)

            # 안내 메시지
            instruction_label = Label(self.selection_window, text="드래그하여 영역을 선택하고, Esc 키를 눌러 종료합니다.", bg="yellow", fg="black")
            instruction_label.place(x=10, y=10)
            
            self.selection_window.protocol("WM_DELETE_WINDOW", self._close_selection_window)
            print("DEBUG: 선택 창 표시 완료 (리사이즈 적용됨)")

        except Exception as e:
            print(f"ERROR: 선택 창 표시 중 오류 발생: {e}")
            self._close_selection_window()

    def _on_button_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)

    def _on_mouse_drag(self, event):
        self.current_x = self.canvas.canvasx(event.x)
        self.current_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect_id, self.start_x, self.start_y, self.current_x, self.current_y)

    def _on_button_release(self, event):
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)

        # 선택 영역 정규화 (항상 start < end)
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        # 최소 크기 체크
        if (x2 - x1 < 10) or (y2 - y1 < 10):
            self._close_selection_window()
            return

        # 좌표 변환 (보여지는 좌표 -> 원본 이미지 좌표)
        real_x1 = int(x1 * self.scale_x)
        real_y1 = int(y1 * self.scale_y)
        real_x2 = int(x2 * self.scale_x)
        real_y2 = int(y2 * self.scale_y)
        
        print(f"DEBUG: 자르기 좌표 변환: ({x1}, {y1}) -> ({real_x1}, {real_y1})")

        # 이미지 잘라내기 (원본에서)
        cropped_image = self.original_image.crop((real_x1, real_y1, real_x2, real_y2))

        # [수정] Retina 디스플레이 대응: 리사이즈 제거
        # pyautogui는 화면 스캔 시 Retina 해상도(2x)를 기준으로 비교하므로,
        # 원본(2x) 이미지를 그대로 저장해야 정확한 매칭이 가능함.
        # 좌표 보정은 main_gui.py의 _click 메서드에서 처리함.
        
        # 사용자에게 이름과 딜레이 입력받기
        self._get_action_details(cropped_image)





    def _get_action_details(self, cropped_image):
        print("DEBUG: 이미지 크롭 완료, 정보 입력 다이얼로그 준비")
        
        # [수정] 튕김 방지: 선택 창을 완전히 닫고 메인 윈도우 갱신 후 다이얼로그 호출
        if self.selection_window:
            self.selection_window.destroy()
            self.selection_window = None
        
        # 메인 윈도우가 다시 활성화되고 그려질 시간을 줌
        if self.master:
            self.master.update()
            # self.master.deiconify() # 필요시 주석 해제

        try:
            action_name = simpledialog.askstring("동작 설정", "이 동작의 이름을 입력하세요:", parent=self.master)
            if not action_name:
                # 취소 누르면 저장하지 않음 (또는 기본값 사용)
                print("DEBUG: 이름 입력 취소됨")
                return 

            delay_str = simpledialog.askstring("동작 설정", f"'{action_name}' 동작 후 대기 시간(초)을 입력하세요:", initialvalue="1", parent=self.master)
            try:
                delay = float(delay_str)
            except (ValueError, TypeError):
                delay = 1.0 # 유효하지 않으면 기본값

            # 파일 저장 (절대 경로 사용)
            images_dir = os.path.join(self.base_dir, "images")
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)

            image_filename = f"{action_name}_{int(time.time())}.png"
            image_save_path = os.path.join(images_dir, image_filename)
            cropped_image.save(image_save_path)
            print(f"DEBUG: 이미지 저장 완료 -> {image_save_path}")

            # 메인 앱으로 선택된 이미지 정보 전달
            self.on_image_selected(action_name, image_save_path, delay)
            
        except Exception as e:
            print(f"ERROR: 정보 입력 중 오류 발생: {e}")
        
        # 임시 파일 정리
        if os.path.exists(self.temp_screenshot_path):
            try:
                os.remove(self.temp_screenshot_path)
            except:
                pass


    def _close_selection_window(self, event=None):
        if self.selection_window:
            self.selection_window.destroy()
            self.selection_window = None
        if os.path.exists(self.temp_screenshot_path):
            os.remove(self.temp_screenshot_path)
        # self.master.deiconify() # 마스터 윈도우 다시 보이기 (숨겼다면)

# 테스트 코드 (실제 앱에서는 사용하지 않음)
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Main App (Hidden)")
    root.geometry("200x100")
    # root.withdraw() # 메인 앱을 숨길 경우

    def handle_selected_image(name, path, delay):
        print(f"선택된 이미지 - 이름: {name}, 경로: {path}, 딜레이: {delay}")
        root.destroy()

    def start_capture():
        capture_tool = ScreenCaptureTool(root, handle_selected_image)
        capture_tool.capture_and_select()

    btn = Button(root, text="캡처 시작", command=start_capture)
    btn.pack()

    root.mainloop()
