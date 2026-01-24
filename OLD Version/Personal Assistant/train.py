# train.py
import subprocess
import sys


def train_model():
    print("Starting model training...")

    # This command runs the spaCy training process
    command = [
        sys.executable,  # Gets the path to your python.exe
        "-m", "spacy",
        "train",
        "config.cfg",  # Use the FINAL config file
        "--output", "./models",
        "--paths.train", "./train.spacy",
        "--paths.dev", "./dev.spacy",
        "--gpu-id", "-1"  # Force CPU training (set to 0 if you have a GPU)
    ]

    # Run the command and print output as it comes
    # Added error checking
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                   encoding='utf-8')

        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())

        rc = process.poll()
        if rc == 0:
            print("\n✅ Training complete! Model saved in ./models/model-best")
        else:
            print(f"\n❌ Training failed with exit code {rc}")
            print("Please check your config.cfg and data files.")

    except FileNotFoundError:
        print("\n❌ Error: 'spacy' command not found.")
        print("Is spaCy installed correctly in your virtual environment?")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")


if __name__ == "__main__":
    train_model()