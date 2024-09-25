from moviepy.editor import VideoFileClip


def extract_audio(video_path, audio_output_path):
    # 加载视频文件
    video = VideoFileClip(video_path)
    # 提取音频
    audio = video.audio
    # 将音频保存到指定文件
    audio.write_audiofile(audio_output_path)


# 示例用法
video_file = "a.mp4"  # 输入视频文件路径
audio_output = "output_audio.mp3"  # 输出音频文件路径
from faster_whisper import WhisperModel

model_size = "large-v3"

# Run on GPU with FP16
# model = WhisperModel(model_size)

# or run on GPU with INT8
# model = WhisperModel(model_size, device="cuda", compute_type="int8_float16")
# or run on CPU with INT8
model = WhisperModel(model_size, device="cpu", compute_type="int8")
segments, info = model.transcribe(r"D:\pythonProject\utils\output_audio.mp3")


def generate_srt(transcript, output_path):
    lines = transcript
    with open(output_path, "w") as srt_file:
        for i, line in enumerate(lines):
            srt_file.write(f"{i + 1}\n")
            srt_file.write(f"00:00:{int(line.start):02d},000 --> 00:00:{int(line.end):02d},000\n")
            srt_file.write(f"{line.text.strip()}\n\n")


# 示例
generate_srt(segments, "output_subtitles.srt")
# 命令行运行
'ffmpeg -i a.mp4 -vf subtitles=output_subtitles.srt output_video.mp4'
