// Collect actual fonts for each visible body text run without changing the DOM.
async function captureFonts(page, snapshot, ready) {
  const result = { status: 'verified', samples: [], errors: [] };
  if (!ready) result.errors.push('Font loading did not settle before capture');

  let session;
  try {
    session = await page.context().newCDPSession(page);
    await session.send('DOM.enable');
    await session.send('CSS.enable');
    const { root } = await session.send('DOM.getDocument', { depth: -1, pierce: true });

    async function inspect(sample) {
      const measured = { ...sample, fonts: [] };
      try {
        let rootId = root.nodeId;
        for (const host of sample.shadow_hosts) {
          const { nodeId } = await session.send('DOM.querySelector', { nodeId: rootId, selector: host });
          const { node } = await session.send('DOM.describeNode', { nodeId, depth: 1, pierce: true });
          const shadow = (node.shadowRoots || []).find(item => item.shadowRootType === 'open');
          if (!shadow) throw Error('Open shadow root is unavailable');
          rootId = shadow.nodeId;
        }
        const { nodeId } = await session.send('DOM.querySelector', { nodeId: rootId, selector: sample.css_path });
        if (!nodeId) throw Error('Text owner is unavailable');
        const { node } = await session.send('DOM.describeNode', { nodeId, depth: 2, pierce: true });
        let targets;
        if (sample.pseudo) {
          const pseudo = (node.pseudoElements || []).find(item => item.pseudoType === sample.pseudo);
          if (!pseudo) throw Error('Rendered pseudo text is unavailable');
          targets = [pseudo];
        } else if (sample.direct_text.length) {
          targets = (node.children || []).filter(item => item.nodeType === 3 && item.nodeValue.trim());
          if (targets.length !== sample.direct_text.length || targets.some((item, index) => item.nodeValue.trim() !== sample.direct_text[index])) {
            throw Error('Text changed during font inspection');
          }
        } else {
          targets = [node]; // Input values and placeholders use browser-owned text.
        }
        for (const target of targets) {
          const { fonts } = await session.send('CSS.getPlatformFontsForNode', { nodeId: target.nodeId });
          measured.fonts.push(...fonts.filter(font => font.glyphCount > 0));
        }
        if (!measured.fonts.length) throw Error('Actual rendered glyph fonts were not reported');
      } catch (error) {
        measured.error = String(error);
        result.errors.push(sample.selector + ': ' + measured.error);
      }
      result.samples.push(measured);
    }

    const queue = [...(snapshot.body_text_samples || [])];
    async function worker() {
      while (queue.length) {
        const sample = queue.shift();
        if (sample) await inspect(sample);
      }
    }
    await Promise.all(Array.from({ length: Math.min(8, queue.length) }, worker));
  } catch (error) {
    result.errors.push('Platform font inspection unavailable: ' + String(error));
  } finally {
    if (session) await session.detach();
  }
  if (result.errors.length) result.status = 'unverified';
  return result;
}

module.exports = { captureFonts };
