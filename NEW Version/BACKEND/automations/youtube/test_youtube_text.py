# BACKEND/automations/youtube/test_youtube_text.py
from BACKEND.automations.browser.browser_config import (
    get_browser_choice,
    save_browser_choice
)
from BACKEND.automations.youtube.yt_controller import YouTubeController


def ask_browser_choice():
    print("\nChoose browser for automation:")
    print("1. Chrome")
    print("2. Edge")

    while True:
        choice = input("Enter choice (1/2): ").strip()
        if choice == "1":
            save_browser_choice("chrome")
            return
        elif choice == "2":
            save_browser_choice("edge")
            return
        else:
            print("Invalid choice. Please enter 1 or 2.")


def print_commands():
    print("\nAvailable commands:")
    print("────────────────────────────────")
    print("SEARCH / PLAY")
    print("  search <query>          → Search only")
    print("  play <query>            → Play first video")
    print("")
    print("PLAYBACK")
    print("  play pause")
    print("  pause")
    print("  resume")
    print("  stop")
    print("  restart")
    print("")
    print("VOLUME")
    print("  volume up")
    print("  volume down")
    print("  mute")
    print("  unmute")
    print("")
    print("SEEK")
    print("  seek forward")
    print("  seek backward")
    print("  seek start")
    print("  seek end")
    print("")
    print("SPEED")
    print("  speed up")
    print("  speed down")
    print("  speed <0.25–2.0>")
    print("")
    print("VIEW")
    print("  fullscreen")
    print("  exit fullscreen")
    print("  theater mode")
    print("")
    print("CAPTIONS")
    print("  captions")
    print("")
    print("SYSTEM")
    print("  help")
    print("  exit")
    print("────────────────────────────────")


def main():
    print("\n=== YouTube Automation Test (Text Mode) ===")

    # ---- First run: ask browser ----
    if not get_browser_choice():
        ask_browser_choice()

    try:
        yt = YouTubeController()
    except Exception as e:
        print("\n❌ Automation unavailable:")
        print(str(e))
        print("⚠️ Please reinstall Chrome/Edge and try again.")
        return

    print("\n✅ YouTube automation ready.")
    print_commands()

    while True:
        cmd = input("\n> ").strip().lower()

        try:
            # -------- SEARCH / PLAY --------
            if cmd.startswith("play "):
                yt.play(cmd.replace("play ", "").strip())

            elif cmd.startswith("search "):
                yt.search(cmd.replace("search ", "").strip())

            # -------- PLAYBACK --------
            elif cmd == "play pause":
                yt.play_pause()

            elif cmd == "pause":
                yt.pause()

            elif cmd == "resume":
                yt.resume()

            elif cmd == "stop":
                yt.stop()

            elif cmd == "restart":
                yt.restart()

            # -------- VOLUME --------
            elif cmd == "volume up":
                yt.volume_up()

            elif cmd == "volume down":
                yt.volume_down()

            elif cmd == "mute":
                yt.mute()

            elif cmd == "unmute":
                yt.unmute()

            # -------- SEEK --------
            elif cmd == "seek forward":
                yt.seek_forward()

            elif cmd == "seek backward":
                yt.seek_backward()

            elif cmd == "seek start":
                yt.seek_start()

            elif cmd == "seek end":
                yt.seek_end()

            # -------- SPEED --------
            elif cmd == "speed up":
                yt.speed_up()

            elif cmd == "speed down":
                yt.speed_down()

            elif cmd.startswith("speed "):
                speed = float(cmd.replace("speed ", "").strip())
                yt.set_speed(speed)

            # -------- VIEW --------
            elif cmd == "fullscreen":
                yt.fullscreen()

            elif cmd == "exit fullscreen":
                yt.exit_fullscreen()

            elif cmd == "theater mode":
                yt.theater_mode()

            # -------- CAPTIONS --------
            elif cmd == "captions":
                yt.captions()

            # -------- SYSTEM --------
            elif cmd == "help":
                print_commands()

            elif cmd == "exit":
                yt.close()
                print("👋 Test ended.")
                break

            else:
                print("Unknown command. Type 'help' to see all commands.")

        except Exception as e:
            print("❌ Command failed:", e)


if __name__ == "__main__":
    main()
