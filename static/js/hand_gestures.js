(function () {
  const DEBUG = true;
  const flashcardReview = document.getElementById('quiz-modal');
  const enableButton = document.getElementById('gesture-toggle');
  const stopButton = document.getElementById('gesture-stop');
  const status = document.getElementById('gesture-status');
  const video = document.getElementById('gesture-video');
  if (!flashcardReview || !enableButton || !stopButton || !status || !video) return;

  function debug(...values) {
    if (DEBUG) console.log('[hand-gesture]', ...values);
  }
  window.studyflowGestureDebug = debug;

  const mobileUserAgent = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
  const coarseTouchDevice = navigator.maxTouchPoints > 0 &&
    window.matchMedia('(pointer: coarse)').matches;
  if (mobileUserAgent || coarseTouchDevice) {
    enableButton.classList.add('hidden');
    stopButton.classList.add('hidden');
    status.textContent = 'Gesture control is available on desktop only.';
    video.classList.add('hidden');
    return;
  }

  let stream = null;
  let tracker = null;
  let frameId = null;
  let active = false;
  let heldGesture = '';
  let handXHistory = [];
  let heldFrames = 0;
  let gestureHandled = false;
  let gestureCooldownUntil = 0;
  let trackingState = '';

  function report(message) {
    status.textContent = message;
  }

  function reportActionResult(result, fallback) {
    if (result && typeof result.then === 'function') {
      report('Saving flashcard review...');
      result.then((message) => {
        if (active && message) report(message);
        debug('action ran:', message || fallback);
      }).catch(() => {
        if (active) report('Could not save that review. Check your connection and try again.');
      });
      return;
    }
    debug('action ran:', result || fallback);
    report(result || fallback);
  }

  function countExtendedFingers(landmarks) {
    return [8, 12, 16, 20].filter((tip) => landmarks[tip].y < landmarks[tip - 2].y).length;
  }

  function detectPose(landmarks) {
    const extended = countExtendedFingers(landmarks);
    const otherFingersCurled = extended <= 1;
    const thumbUp = landmarks[4].y < landmarks[3].y - 0.05;
    const thumbDown = landmarks[4].y > landmarks[3].y + 0.05;

    if (thumbUp && otherFingersCurled) return 'thumbs-up';
    if (thumbDown && otherFingersCurled) return 'thumbs-down';
    if (extended >= 4) return 'palm';
    if (extended <= 1) return 'fist';
    return '';
  }

  function performHeldGesture(pose) {
    if (pose === 'palm') {
      if (typeof window.studyflowGestureOpenPalm === 'function') {
        reportActionResult(window.studyflowGestureOpenPalm(), 'Open palm detected.');
      }
      return;
    }

    if (pose === 'fist') {
      if (typeof window.studyflowGestureClosePalm === 'function') {
        reportActionResult(window.studyflowGestureClosePalm(), 'Closed fist: answer hidden.');
      }
      return;
    }

    const actions = {
      'thumbs-up': ['studyflowGestureThumbsUp', 'Thumbs up: I knew it.'],
      'thumbs-down': ['studyflowGestureThumbsDown', 'Thumbs down: I forgot.'],
    };
    const action = actions[pose];
    if (action && typeof window[action[0]] === 'function') {
      reportActionResult(window[action[0]](), action[1]);
    }
  }

  function onResults(results) {
    if (!active || !results.multiHandLandmarks || !results.multiHandLandmarks.length) {
      heldGesture = '';
      heldFrames = 0;
      gestureHandled = false;
      handXHistory = [];
      if (active && trackingState !== 'no-hand') {
        trackingState = 'no-hand';
        report('Camera active; no hand detected. Move your hand into the preview.');
      }
      return;
    }

    if (trackingState !== 'hand') {
      trackingState = 'hand';
      report('Hand detected. Try an open palm, swipe, thumbs-up, or pinch.');
    }

    const landmarks = results.multiHandLandmarks[0];
    const now = performance.now();
    const handX = landmarks[0].x;
    handXHistory.push({ x: handX, time: now, open: countExtendedFingers(landmarks) >= 3 });
    while (handXHistory.length > 10 ||
           (handXHistory.length > 1 && now - handXHistory[0].time > 400)) {
      handXHistory.shift();
    }

    if (handXHistory.length > 1) {
      const deltaX = handX - handXHistory[0].x;
      if (handXHistory.length % 3 === 0) debug('current hand x:', handX, 'x delta:', deltaX);
      const openFrames = handXHistory.filter(frame => frame.open).length;
      const mostlyOpen = openFrames >= Math.ceil(handXHistory.length * 0.6);
      if (mostlyOpen && handXHistory.length >= 3 && Math.abs(deltaX) >= 0.15 &&
          now - handXHistory[0].time <= 400 && now >= gestureCooldownUntil) {
        const direction = deltaX > 0 ? 1 : -1;
        const label = direction > 0 ? 'Swipe right ->' : 'Swipe left ->';
        debug('detected gesture:', label, 'x delta:', deltaX);
        gestureCooldownUntil = now + 700;
        handXHistory = [];
        heldGesture = 'palm';
        heldFrames = 3;
        gestureHandled = true;
        if (typeof window.studyflowFlashcardSwipe === 'function') {
          const outcome = window.studyflowFlashcardSwipe(direction);
          report(`${label} ${outcome || (direction > 0 ? 'next card' : 'previous card')}`);
        } else {
          report(`${label} flashcard navigation is unavailable.`);
        }
        return;
      }
    }

    if (now < gestureCooldownUntil) return;
    const pose = detectPose(landmarks);

    if (pose) {
      if (pose !== heldGesture) {
        heldGesture = pose;
        heldFrames = 1;
        gestureHandled = false;
        const prompts = {
          palm: 'Open palm -> show answer',
          fist: 'Closed fist -> hide answer',
          'thumbs-up': 'Thumbs up -> I knew it',
          'thumbs-down': 'Thumbs down -> I forgot',
        };
        report(prompts[pose] || 'Gesture detected.');
      } else {
        heldFrames += 1;
      }
      if (heldFrames >= 3 && !gestureHandled) {
        gestureHandled = true;
        gestureCooldownUntil = now + 700;
        debug('detected gesture:', pose);
        performHeldGesture(pose);
      }
      return;
    }

    heldGesture = '';
    heldFrames = 0;
    gestureHandled = false;
  }

  async function processFrames() {
    if (!active) return;
    try {
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
        await tracker.send({ image: video });
      }
      if (active) frameId = requestAnimationFrame(processFrames);
    } catch (error) {
      await disable('Hand tracking stopped unexpectedly. Turn gestures off, then enable them again.');
    }
  }

  async function disable(message = 'Off. Camera stopped.') {
    active = false;
    if (frameId) cancelAnimationFrame(frameId);
    frameId = null;
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
    video.classList.add('hidden');
    if (tracker) {
      try {
        await tracker.close();
      } catch (error) {
        debug('tracker close failed:', error);
      }
    }
    tracker = null;
    stopButton.classList.add('hidden');
    enableButton.classList.remove('hidden');
    enableButton.setAttribute('aria-pressed', 'false');
    report(message);
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
      debug('video ready:', video.videoWidth, video.videoHeight);
      tracker = new window.Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`,
      });
      tracker.setOptions({ maxNumHands: 1, modelComplexity: 0, minDetectionConfidence: 0.65, minTrackingConfidence: 0.65 });
      tracker.onResults(onResults);
      debug('model loaded: MediaPipe Hands');
      active = true;
      trackingState = '';
      enableButton.classList.add('hidden');
      enableButton.setAttribute('aria-pressed', 'true');
      stopButton.classList.remove('hidden');
      enableButton.disabled = false;
      report('Camera ready. Show your hand to begin.');
      stream.getVideoTracks().forEach((track) => {
        track.addEventListener('ended', async () => {
          if (active) await disable("Your camera isn't turned on. Turn it on to use gesture control.");
        }, { once: true });
      });
      frameId = requestAnimationFrame(processFrames);
    } catch (error) {
      const message = error.name === 'NotAllowedError'
        ? 'Camera access is blocked. Allow camera access in your browser settings to use gesture control.'
        : error.name === 'NotFoundError'
          ? 'No camera found. Connect a webcam to use gesture control.'
          : error.name === 'NotReadableError'
            ? 'Your camera is being used by another app. Close it and try again.'
            : 'Could not start the camera. Check browser permissions and try again.';
      await disable(message);
    } finally {
      enableButton.disabled = false;
    }
  }

  enableButton.addEventListener('click', enable);
  stopButton.addEventListener('click', () => disable());
  window.addEventListener('pagehide', () => disable());
  window.addEventListener('beforeunload', () => disable());
})();