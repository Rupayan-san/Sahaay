import { FormEvent, useMemo, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AudioLines, FileAudio, FileText, ImagePlus, Loader2, UploadCloud } from 'lucide-react';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import { ingestAndCreateIssue } from '../api/issues';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { useAppStore } from '../store/useAppStore';

type InputTab = 'text' | 'image' | 'audio';

function UploadPanel({
  accept,
  file,
  helperText,
  icon,
  inputLabel,
  isActive,
  onDragStateChange,
  onFileSelect,
}: {
  accept: string;
  file: File | null;
  helperText: string;
  icon: React.ReactNode;
  inputLabel: string;
  isActive: boolean;
  onDragStateChange: (active: boolean) => void;
  onFileSelect: (file: File | null) => void;
}) {
  return (
    <label
      className={`flex min-h-[240px] cursor-pointer flex-col items-center justify-center rounded-[28px] border-2 border-dashed p-6 text-center transition ${
        isActive
          ? 'border-primary bg-primary/5 dark:bg-primary/10'
          : 'border-outline-variant bg-white hover:border-primary/40 hover:bg-surface-container-low dark:border-gray-800 dark:bg-gray-900 dark:hover:bg-gray-900/80'
      }`}
      onDragOver={(event) => {
        event.preventDefault();
        onDragStateChange(true);
      }}
      onDragEnter={(event) => {
        event.preventDefault();
        onDragStateChange(true);
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        onDragStateChange(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        onDragStateChange(false);
        onFileSelect(event.dataTransfer.files?.[0] ?? null);
      }}
    >
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-3xl bg-primary text-white shadow-lg">
        {icon}
      </div>
      <p className="text-lg font-semibold text-on-surface dark:text-gray-100">
        {file ? file.name : 'Drag and drop a file here'}
      </p>
      <p className="mt-2 max-w-sm text-sm text-on-surface-variant dark:text-gray-400">{helperText}</p>
      <div className="mt-5 inline-flex items-center gap-2 rounded-full bg-surface-container px-4 py-2 text-sm font-medium text-on-surface dark:bg-gray-800 dark:text-gray-200">
        <UploadCloud size={16} />
        Choose file
      </div>
      <input
        type="file"
        accept={accept}
        aria-label={inputLabel}
        className="hidden"
        onChange={(event) => onFileSelect(event.target.files?.[0] ?? null)}
      />
    </label>
  );
}

export function DataInput() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { setLastExtractedIssue } = useAppStore();
  const [activeTab, setActiveTab] = useState<InputTab>('text');
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState('');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [draggingTab, setDraggingTab] = useState<InputTab | null>(null);

  const imagePreview = useMemo(
    () => (imageFile ? URL.createObjectURL(imageFile) : null),
    [imageFile],
  );
  const ingestMutation = useMutation({
    mutationFn: ingestAndCreateIssue,
    onSuccess: ({ ingestResult, issue, matched_existing }) => {
      setLastExtractedIssue(issue);
      queryClient.invalidateQueries({ queryKey: ['issues'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      toast.success(matched_existing ? 'Existing issue updated' : 'Issue created successfully');
      navigate('/extraction', {
        state: {
          issue,
          matched_existing,
          ingestResult,
        },
      });
    },
  });
  const isTextSubmitDisabled =
    ingestMutation.isPending || description.trim().length < 10 || !location.trim();

  const handleTextSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!description.trim()) {
      toast.error('Please describe the issue.');
      return;
    }
    if (!location.trim()) {
      toast.error('Please add a location.');
      return;
    }

    ingestMutation.mutate({
      type: 'text',
      text: `${description.trim()}\nLocation: ${location.trim()}`,
    });
  };

  const handleFileSubmit = (tab: Extract<InputTab, 'image' | 'audio'>) => {
    const file = tab === 'image' ? imageFile : audioFile;
    if (!file) {
      toast.error(`Please select a ${tab} file.`);
      return;
    }

    ingestMutation.mutate({
      type: tab,
      file,
    });
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <section className="rounded-[32px] bg-primary px-6 py-8 text-white shadow-xl sm:px-8">
        <p className="label-caps text-white/70">Step 1</p>
        <h2 className="mt-3 max-w-2xl font-heading text-3xl font-bold tracking-tight sm:text-4xl">
          Capture a community issue from text, images, or voice.
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-white/80 sm:text-base">
          Sahaay will ingest the report, extract the issue details, and route you into the matching workflow.
        </p>
      </section>

      <div className="rounded-[28px] border border-outline-variant bg-surface-container-low p-2 dark:border-gray-800 dark:bg-gray-900/70">
        <div className="grid gap-2 sm:grid-cols-3">
          {[
            { value: 'text' as const, label: 'Text Report', icon: FileText },
            { value: 'image' as const, label: 'Upload Image', icon: ImagePlus },
            { value: 'audio' as const, label: 'Upload Audio', icon: AudioLines },
          ].map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              type="button"
              onClick={() => setActiveTab(value)}
              className={`flex items-center justify-center gap-2 rounded-[22px] px-4 py-3 text-sm font-semibold transition ${
                activeTab === value
                  ? 'bg-white text-primary shadow-sm dark:bg-gray-950 dark:text-white'
                  : 'text-on-surface-variant hover:bg-white/60 dark:text-gray-400 dark:hover:bg-gray-950/50'
              }`}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {ingestMutation.isPending ? (
        <div className="card p-10">
          <LoadingSpinner size={38} message="Processing the report and extracting issue details..." />
        </div>
      ) : null}

      {activeTab === 'text' ? (
        <form onSubmit={handleTextSubmit} className="card grid gap-6 p-6 sm:p-8 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-5">
            <div>
              <label
                htmlFor="issue-description"
                className="label-caps mb-2 block text-on-surface-variant dark:text-gray-400"
              >
                Raw description
              </label>
              <textarea
                id="issue-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Describe what happened, who is affected, and what support is needed."
                rows={8}
                className="input-field min-h-[220px] resize-none"
              />
            </div>
            <div>
              <label
                htmlFor="issue-location"
                className="label-caps mb-2 block text-on-surface-variant dark:text-gray-400"
              >
                Location
              </label>
              <input
                id="issue-location"
                value={location}
                onChange={(event) => setLocation(event.target.value)}
                placeholder="Village, neighborhood, or landmark"
                className="input-field"
              />
            </div>
            <button
              type="submit"
              className="btn-primary inline-flex w-full items-center justify-center gap-2 py-3"
              disabled={isTextSubmitDisabled}
            >
              {ingestMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
              Process text report
            </button>
          </div>

          <div className="rounded-[28px] bg-surface-container p-6 dark:bg-gray-950/70">
            <p className="label-caps text-on-surface-variant dark:text-gray-500">Tips</p>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-on-surface dark:text-gray-200">
              <li>Include what is broken, urgent, or blocked.</li>
              <li>Mention the exact place so matching works better.</li>
              <li>Use plain language. Gemini will structure the issue for you.</li>
            </ul>
          </div>
        </form>
      ) : null}

      {activeTab === 'image' ? (
        <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="card p-6 sm:p-8">
            <UploadPanel
              accept="image/*"
              file={imageFile}
              helperText="Upload a photo of the issue. OCR and metadata extraction will run automatically."
              icon={<ImagePlus size={26} />}
              inputLabel="Image upload"
              isActive={draggingTab === 'image'}
              onDragStateChange={(active) => setDraggingTab(active ? 'image' : null)}
              onFileSelect={setImageFile}
            />
            <button
              type="button"
              onClick={() => handleFileSubmit('image')}
              className="btn-primary mt-5 inline-flex w-full items-center justify-center gap-2 py-3"
              disabled={!imageFile || ingestMutation.isPending}
            >
              <UploadCloud size={16} />
              Upload image
            </button>
          </div>

          <div className="card flex items-center justify-center overflow-hidden p-4">
            {imagePreview ? (
              <img
                src={imagePreview}
                alt="Selected preview"
                className="max-h-[420px] w-full rounded-[24px] object-cover"
              />
            ) : (
              <div className="flex h-full min-h-[260px] w-full flex-col items-center justify-center rounded-[24px] border border-dashed border-outline-variant bg-surface-container text-center dark:border-gray-800 dark:bg-gray-950/60">
                <ImagePlus size={28} className="text-on-surface-variant dark:text-gray-500" />
                <p className="mt-3 text-sm text-on-surface-variant dark:text-gray-400">Image preview will appear here.</p>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {activeTab === 'audio' ? (
        <div className="card grid gap-6 p-6 sm:p-8 lg:grid-cols-[1.1fr_0.9fr]">
          <UploadPanel
            accept="audio/*"
            file={audioFile}
            helperText="Upload a field recording. Whisper transcription will convert speech into report text."
            icon={<FileAudio size={26} />}
            inputLabel="Audio upload"
            isActive={draggingTab === 'audio'}
            onDragStateChange={(active) => setDraggingTab(active ? 'audio' : null)}
            onFileSelect={setAudioFile}
          />

          <div className="flex flex-col justify-between rounded-[28px] bg-surface-container p-6 dark:bg-gray-950/70">
            <div>
              <p className="label-caps text-on-surface-variant dark:text-gray-500">Selected file</p>
              <p className="mt-4 text-lg font-semibold text-on-surface dark:text-gray-100">
                {audioFile?.name ?? 'No file selected'}
              </p>
              <p className="mt-2 text-sm text-on-surface-variant dark:text-gray-400">
                Supported formats: MP3 and WAV. Large files may take longer to process.
              </p>
            </div>

            <button
              type="button"
              onClick={() => handleFileSubmit('audio')}
              className="btn-primary mt-6 inline-flex w-full items-center justify-center gap-2 py-3"
              disabled={!audioFile || ingestMutation.isPending}
            >
              <UploadCloud size={16} />
              Upload audio
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
