(function () {
  const enableButton = document.getElementById('gesture-toggle');
  const stopButton = document.getElementById('gesture-stop');
  const status = document.getElementById('gesture-status');
  const video = document.getElementById('gesture-video');
  if (!enableButton || !stopButton || !status || !video) return;

  let stream = null;
  let tracker = null;
  let frameId = null;
  let active = false;
  let heldGesture = '';
  let heldSince = 0;
  let lastActionAt = 0;
  let swipeOrigin = null;

  function report(message) {
    status.textContent = message;
  }

  function countExtendedFingers(landmarks) {
    return [8, 12, 16, 20].filter((tip) => landmarks[tip].y < landmarks[tip - 2].y).length;
  }

  function onResults(results) {
    if (!active || !results.multiHandLandmarks || !results.multiHandLandmarks.length) {
      heldGesture = '';
      swipeOrigin = null;
      return;
    }

    const landmarks = results.multiHandLandmarks[0];
    const extended = countExtendedFingers(landmarks);
    const pose = extended >= 4 ? 'palm' : extended <= 1 ? 'fist' : '';
    const now = performance.now();

    if (pose) {
      swipeOrigin = null;
      if (pose !== heldGesture) {
        heldGesture = pose;
        heldSince = now;
        report(pose === 'palm' ? 'Open palm detected; hold to pause.' : 'Closed fist detected; hold to resume.');
      } else if (now - heldSince >= 1000 && now - lastActionAt >= 1200) {
        lastActionAt = now;
        if (pose === 'palm') {
          window.studyflowGesturePause?.();
          report('Open palm held: timer paused.');
        } else {
          window.studyflowGestureResume?.();
          report('Closed fist held: timer resumed.');
        }
      }
      return;
    }

    heldGesture = '';
    const wristX = landmarks[0].x;
    if (!swipeOrigin || now - swipeOrigin.time > 650) {
      swipeOrigin = { x: wristX, time: now };
    } else if (Math.abs(wristX - swipeOrigin.x) > 0.22 && now - lastActionAt >= 900) {
      const direction = wristX < swipeOrigin.x ? 1 : -1;
      lastActionAt = now;
      if (typeof window.studyflowFlashcardSwipe === 'function') {
        window.studyflowFlashcardSwipe(direction);
        report(direction > 0 ? 'Swipe left detected: next flashcard.' : 'Swipe right detected: previous flashcard.');
      } else {
        report('Swipe detected. Open a flashcard review to navigate cards.');
      }
      swipeOrigin = null;
    }
  }

  async function processFrames() {
    if (!active || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;
    await tracker.send({ image: video });
    frameId = requestAnimationFrame(processFrames);
  }

  async function disable() {
    active = false;
    if (frameId) cancelAnimationFrame(frameId);
    frameId = null;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    video.classList.add('hidden');
    if (tracker) await tracker.close();
    tracker = null;
    stopButton.classList.add('hidden');
    enableButton.classList.remove('hidden');
    enableButton.setAttribute('aria-pressed', 'false');
    report('Off. Camera stopped.');
  }

  async function enable() {
    if (!navigator.mediaDevices?.getUserMedia || !window.Hands) {
      report('Camera gestures are unavailable in this browser.');
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
      video.srcObject = stream;
      video.classList.remove('hidden');
      await video.play();
      tracker = new window.Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
      });
      tracker.setOptions({ maxNumHands: 1, modelComplexity: 0, minDetectionConfidence: 0.65, minTrackingConfidence: 0.65 });
      tracker.onResults(onResults);
      active = true;
      enableButton.classList.add('hidden');
      enableButton.setAttribute('aria-pressed', 'true');
      stopButton.classList.remove('hidden');
      report('Camera on. Video stays on this device.');
      frameId = requestAnimationFrame(processFrames);
    } catch (error) {
      await disable();
      report(error.name === 'NotAllowedError' ? 'Camera permission was not granted; gestures remain off.' : 'Could not start the camera. Gestures remain off.');
    }
  }

  enableButton.addEventListener('click', enable);
  stopButton.addEventListener('click', disable);
  window.addEventListener('pagehide', disable);
})();