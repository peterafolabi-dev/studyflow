(function () {
  // Enable with ?gesture_debug=1 to log landmark deltas to the console.
  const DEBUG = new URLSearchParams(window.location.search).has('gesture_debug');
  const MEDIAPIPE_HANDS_VERSION = '0.4.1675469240'; // keep in sync with the <script> tag in flashcards.html
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
  let heldFrames = 0;
  let gestureHandled = false;
  let gestureCooldownUntil = 0;
  let trackingState = '';
  let handEverSeen = false;
  let cameraStartedAt = 0;

  // Swipe engine ("traffic warden" rules): one clear sideways movement = one action.
  const SWIPE_WINDOW_MS = 350;      // look at the last 350 ms of palm movement
  const SWIPE_MIN_DX = 0.14;        // at least 14% of the frame width
  const SWIPE_STRAIGHTNESS = 2;     // sideways movement must be 2x the vertical movement
  const REST_SPEED = 0.45;          // frame-widths per second; slower than this = hand at rest
  const REST_FRAMES = 4;            // hand must rest this many frames before the next swipe
  const RETURN_STROKE_MS = 1000;    // opposite-direction movement this soon is the hand coming back
  const STILL_SPEED = 0.6;          // palm/fist/thumb poses only count while the hand is nearly still
  let palmTrack = [];
  let needsRest = false;
  let restFrames = 0;
  let lastSwipeDir = 0;
  let lastSwipeAt = 0;

  // Overlay on the (mirrored) preview: hand outline + a big arrow when a swipe is recognised.
  const previewWrap = document.createElement('div');
  previewWrap.style.cssText = 'position:relative;display:inline-block;margin-top:0.75rem;';
  video.parentNode.insertBefore(previewWrap, video);
  previewWrap.appendChild(video);
  video.style.marginTop = '0';
  const overlay = document.createElement('canvas');
  overlay.setAttribute('aria-hidden', 'true');
  overlay.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none;';
  previewWrap.appendChild(overlay);
  const arrow = document.createElement('div');
  arrow.setAttribute('aria-hidden', 'true');
  arrow.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;' +
    'font:700 1.1rem system-ui,sans-serif;color:#fff;text-shadow:0 2px 6px #000;opacity:0;pointer-events:none;';
  previewWrap.appendChild(arrow);
  const HAND_LINKS = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11],
    [11, 12], [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]];

  function palmCenter(landmarks) {
    const ids = [0, 5, 9, 13, 17];
    return {
      x: ids.reduce((sum, i) => sum + landmarks[i].x, 0) / ids.length,
      y: ids.reduce((sum, i) => sum + landmarks[i].y, 0) / ids.length,
    };
  }

  function drawHand(landmarks, center) {
    const w = overlay.clientWidth;
    const h = overlay.clientHeight;
    if (!w || !h) return;
    const ratio = window.devicePixelRatio || 1;
    if (overlay.width !== Math.round(w * ratio)) {
      overlay.width = Math.round(w * ratio);
      overlay.height = Math.round(h * ratio);
    }
    const ctx = overlay.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!landmarks) return;
    // selfieMode landmarks are already mirror-image, matching the mirrored preview.
    ctx.strokeStyle = needsRest ? 'rgba(148,163,184,0.9)' : 'rgba(167,139,250,0.95)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (const [a, b] of HAND_LINKS) {
      ctx.moveTo(landmarks[a].x * w, landmarks[a].y * h);
      ctx.lineTo(landmarks[b].x * w, landmarks[b].y * h);
    }
    ctx.stroke();
    ctx.fillStyle = '#34d399';
    ctx.beginPath();
    ctx.arc(center.x * w, center.y * h, 4, 0, Math.PI * 2);
    ctx.fill();
  }

  function flashArrow(direction) {
    arrow.textContent = direction > 0 ? '→  Next' : '←  Previous';
    arrow.animate(
      [{ opacity: 0, transform: `translateX(${-direction * 24}px)` },
        { opacity: 1, transform: 'translateX(0)', offset: 0.3 },
        { opacity: 0, transform: `translateX(${direction * 24}px)` }],
      { duration: 650, easing: 'ease-out' }
    );
  }

  // Slide the card that changed in the same direction the hand moved.
  function slideCard(direction) {
    const modal = document.getElementById('quiz-modal');
    const target = modal && modal.style.display === 'flex'
      ? document.getElementById('quiz-card')
      : document.querySelector('.sf-flashcard.gesture-current');
    if (!target || !target.animate) return;
    target.animate(
      [{ transform: `translateX(${-direction * 60}px)`, opacity: 0.2 },
        { transform: 'translateX(0)', opacity: 1 }],
      { duration: 260, easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)' }
    );
  }

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

  function distance(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  // A finger is extended when its tip is clearly farther from the wrist than its middle
  // joint. Unlike comparing y values, this works whatever angle the hand is held at.
  function countExtendedFingers(landmarks) {
    const wrist = landmarks[0];
    return [8, 12, 16, 20].filter(
      (tip) => distance(landmarks[tip], wrist) > distance(landmarks[tip - 2], wrist) * 1.15
    ).length;
  }

  function detectPose(landmarks) {
    const extended = countExtendedFingers(landmarks);
    const otherFingersCurled = extended === 0;
    // Hand size (wrist to middle-finger knuckle) makes thresholds independent of camera distance.
    const handSize = distance(landmarks[0], landmarks[9]) || 1;
    // A tucked thumb in a normal fist stays close to the index knuckle; only a thumb that
    // is clearly sticking out counts, so a fist is never misread as thumbs-down.
    const thumbOut = distance(landmarks[4], landmarks[5]) > handSize * 0.55;
    const thumbRise = (landmarks[2].y - landmarks[4].y) / handSize; // + when tip is above its base
    const thumbVertical = Math.abs(landmarks[4].y - landmarks[2].y) > Math.abs(landmarks[4].x - landmarks[2].x);

    if (thumbOut && thumbVertical && otherFingersCurled && thumbRise > 0.4) return 'thumbs-up';
    if (thumbOut && thumbVertical && otherFingersCurled && thumbRise < -0.4) return 'thumbs-down';
    if (extended >= 4) return 'palm';
    if (extended === 0 && !thumbOut) return 'fist';
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
      palmTrack = [];
      needsRest = false;  // taking the hand out of view also re-arms swipes
      restFrames = 0;
      drawHand(null);
      if (active && trackingState !== 'no-hand' && trackingState !== 'no-hand-hint') {
        trackingState = 'no-hand';
        report('Camera active; no hand detected. Move your hand into the preview.');
      }
      // A grey preview with a camera icon means the laptop's camera key/privacy shutter is off;
      // after a while with no hand ever seen, say so instead of leaving people guessing.
      if (active && !handEverSeen && cameraStartedAt && performance.now() - cameraStartedAt > 8000 &&
          trackingState !== 'no-hand-hint') {
        trackingState = 'no-hand-hint';
        report("Still no hand detected. If the preview is grey or shows a camera icon, your laptop's camera is switched off — press the camera key (often F8/F10/F12) or open the privacy shutter.");
      }
      return;
    }

    handEverSeen = true;
    if (trackingState !== 'hand') {
      trackingState = 'hand';
      report('Hand detected. Try an open palm, fist, swipe, or thumbs up/down.');
    }

    const landmarks = results.multiHandLandmarks[0];
    const now = performance.now();
    const center = palmCenter(landmarks);
    drawHand(landmarks, center);

    palmTrack.push({ x: center.x, y: center.y, t: now });
    while (palmTrack.length > 1 && now - palmTrack[0].t > SWIPE_WINDOW_MS) palmTrack.shift();
    const prev = palmTrack.length > 1 ? palmTrack[palmTrack.length - 2] : null;
    const speed = prev ? Math.hypot(center.x - prev.x, center.y - prev.y) / Math.max(1, now - prev.t) * 1000 : 0;

    // After a swipe the hand must settle before another swipe counts (no double fires).
    if (needsRest) {
      restFrames = speed < REST_SPEED ? restFrames + 1 : 0;
      if (restFrames >= REST_FRAMES) {
        needsRest = false;
        palmTrack = [{ x: center.x, y: center.y, t: now }];
      }
      return;
    }

    const first = palmTrack[0];
    const dx = center.x - first.x;   // + = the user's own right (selfieMode mirrors the image)
    const dy = center.y - first.y;
    const isSwipe = palmTrack.length >= 3 && now - first.t >= 80 &&
      Math.abs(dx) >= SWIPE_MIN_DX && Math.abs(dx) >= SWIPE_STRAIGHTNESS * Math.abs(dy) &&
      detectPose(landmarks) !== 'fist';
    if (isSwipe) {
      const direction = dx > 0 ? 1 : -1;
      const isReturnStroke = direction === -lastSwipeDir && now - lastSwipeAt < RETURN_STROKE_MS;
      needsRest = true;
      restFrames = 0;
      palmTrack = [];
      // The hand shape used to swipe (usually an open palm) counts as already used, so holding
      // it still afterwards doesn't flip the card; a pose fires only when the hand changes to it.
      heldGesture = detectPose(landmarks) || '';
      heldFrames = 0;
      gestureHandled = true;
      if (isReturnStroke) {
        debug('ignored return stroke', dx);
        return;
      }
      lastSwipeDir = direction;
      lastSwipeAt = now;
      const label = direction > 0 ? 'Swipe right →' : 'Swipe left ←';
      debug('detected gesture:', label, 'dx:', dx.toFixed(3), 'dy:', dy.toFixed(3));
      flashArrow(direction);
      if (typeof window.studyflowFlashcardSwipe === 'function') {
        const outcome = window.studyflowFlashcardSwipe(direction);
        slideCard(direction);
        report(outcome || `${label} ${direction > 0 ? 'next card' : 'previous card'}`);
      } else {
        report(`${label} flashcard navigation is unavailable.`);
      }
      return;
    }

    // Poses only count while the hand is nearly still, so a swipe never triggers a flip.
    if (speed > STILL_SPEED) {
      heldFrames = 0;
      return;
    }
    if (now < gestureCooldownUntil) return;
    const pose = detectPose(landmarks);

    if (pose) {
      if (pose !== heldGesture) {
        heldGesture = pose;
        heldFrames = 1;
        gestureHandled = false;
        const prompts = {
          palm: 'Open palm → show answer',
          fist: 'Closed fist → hide answer',
          'thumbs-up': 'Thumbs up → I knew it',
          'thumbs-down': 'Thumbs down → I forgot',
        };
        report(prompts[pose] || 'Gesture detected.');
      } else {
        heldFrames += 1;
      }
      if (heldFrames >= 4 && !gestureHandled) {
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
    drawHand(null);
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
      // Hand tracking doesn't need HD; a small frame keeps it smooth on modest laptops.
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
      });
      video.srcObject = stream;
      video.classList.remove('hidden');
      await video.play();
      debug('video ready:', video.videoWidth, video.videoHeight);
      tracker = new window.Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands@${MEDIAPIPE_HANDS_VERSION}/${file}`,
      });
      tracker.setOptions({
        selfieMode: true, // mirror like the preview, so "swipe right" means the user's right
        maxNumHands: 1, modelComplexity: 0, minDetectionConfidence: 0.65, minTrackingConfidence: 0.65,
      });
      tracker.onResults(onResults);
      debug('model loaded: MediaPipe Hands');
      active = true;
      trackingState = '';
      handEverSeen = false;
      cameraStartedAt = performance.now();
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