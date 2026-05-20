export async function loadSamples() {
  const response = await fetch("/api/samples");
  return response.json();
}

export function analyzeSample(sampleId) {
  return fetch(`/api/analyze?sample=${encodeURIComponent(sampleId)}`);
}

export function analyzeContent(filename, content) {
  return fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ filename, content }),
  });
}
