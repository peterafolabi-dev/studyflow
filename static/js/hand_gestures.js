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
  let poseActionTriggered = false;
  let lastActionAt = 0;
  let swipeOrigin = null;

  function report(message) {
    status.textContent = message;
  }

  function countExtendedFingers(landmarks) {
    return [8, 12, 16, 20].filter((tip) => landmarks[tip].y < landmarks[tip - 2].y).length;
  }

  function distanceBetween(first, second) {
    return Math.hypot(first.x - second.x, first.y - second.y);
  }

  function detectPose(landmarks) {
    const extended = countExtendedFingers(landmarks);
    const otherFingersCurled = extended === 0;
    const thumbUp = landmarks[4].y < landmarks[3].y - 0.05;

    if (distanceBetween(landmarks[4], landmarks[8]) < 0.055) return 'pinch';
    if (thumbUp && otherFingersCurled) return 'thumbs-up';
    if (extended >= 4) return 'palm';
    if (extended <= 1) return 'fist';
    return '';
  }

  function performHeldGesture(pose) {
    if (pose === 'palm') {
      if (typeof window.studyflowGestureOpenPalm === 'function') {
        report(window.studyflowGestureOpenPalm() || 'Open palm detected.');
      } else if (typeof window.studyflowGesturePause === 'function') {
        window.studyflowGesturePause();
        report('Open palm held: timer paused.');
      }
      return;
    }

    if (pose === 'fist' && typeof window.studyflowGestureResume === 'function') {
      window.studyflowGestureResume();
      report('Closed fist held: timer resumed.');
      return;
    }

    const actions = {
      'thumbs-up': ['studyflowGestureThumbsUp', 'Thumbs up detected.'],
      pinch: ['studyflowGesturePinch', 'Pinch detected.'],
    };
    const action = actions[pose];
    if (action && typeof window[action[0]] === 'function') {
      report(window[action[0]]() || action[1]);
    }
  }

  function onResults(results) {
    if (!active || !results.multiHandLandmarks || !results.multiHandLandmarks.length) {
      heldGesture = '';
      poseActionTriggered = false;
      swipeOrigin = null;
      return;
    }

    const landmarks = results.multiHandLandmarks[0];
    const pose = detectPose(landmarks);
    const now = performance.now();

    if (pose) {
      swipeOrigin = null;
      if (pose !== heldGesture) {
        heldGesture = pose;
        heldSince = now;
        poseActionTriggered = false;
        const prompts = {
          palm: 'Open palm detected; hold to flip the card.',
          fist: 'Closed fist detected.',
          'thumbs-up': 'Thumbs up detected; hold to mark this card easy.',
          pinch: 'Pinch detected; hold to mark this card reviewed.',
        };
        report(prompts[pose] || 'Gesture detected.');
      } else if (!poseActionTriggered && now - heldSince >= 850 && now - lastActionAt >= 900) {
        lastActionAt = now;
        poseActionTriggered = true;
        performHeldGesture(pose);
      }
      return;
    }

    heldGesture = '';
    poseActionTriggered = false;
    const wristX = landmarks[0].x;
    if (!swipeOrigin || now - swipeOrigin.time > 650) {
      swipeOrigin = { x: wristX, time: now };
    } else if (Math.abs(wristX - swipeOrigin.x) > 0.22 && now - lastActionAt >= 900) {
      const direction = wristX < swipeOrigin.x ? 1 : -1;
      lastActionAt = now;
      if (typeof window.studyflowFlashcardSwipe === 'function') {
        const outcome = window.studyflowFlashcardSwipe(direction);
        report(outcome || 'Swipe detected. Start a flashcard review to navigate cards.');
      } else {
        report('Swipe detected. Open a flashcard review to navigate cards.');
      }
      swipeOrigin = null;
    }
  }

  async function processFrames() {
    if (!active) return;
    try {
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        await tracker.send({ image: video });
      }
      if (active) frameId = requestAnimationFrame(processFrames);
    } catch (error) {
      report('Hand tracking stopped unexpectedly. Turn gestures off, then enable them again.');
      await disable();
    }
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
      report(!navigator.mediaDevices?.getUserMedia
        ? 'This browser or connection does not support camera access. Try a current browser over HTTPS.'
        : 'Hand tracking could not load. Check your connection and reload this page.');
      return;
    }
    enableButton.disabled = true;
    report('Requesting camera permission…');
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: true });
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
      enableButton.disabled = false;
      report('Active & listening... Video stays on this device.');
      frameId = requestAnimationFrame(processFrames);
    } catch (error) {
      await disable();
      report(error.name === 'NotAllowedError'
        ? 'Camera permission was denied. Allow camera access in browser settings, then try again.'
        : error.name === 'NotFoundError'
          ? 'No camera was found. Flashcards still work with the on-screen controls.'
          : 'Could not start the camera. Check browser permissions and try again.');
    } finally {
      enableButton.disabled = false;
    }
  }

  enableButton.addEventListener('click', enable);
  stopButton.addEventListener('click', disable);
  window.addEventListener('pagehide', disable);
})();