// The [slideshow] shortcode's rotation is pure CSS, living in static/blog.css rather than
// in the markup the shortcode returns. Unit tests can only see that markup, so everything
// that decides whether the thing actually rotates -- that the stylesheet is loaded, that
// its data-slides selectors match, that the interval custom property survives calc() -- is
// only observable in a browser. That is what this file is for.
//
// The test data has a page with three slideshows -- one rotating pair of [figure] frames,
// one with more images than the stylesheet has timings for, and one of bare images wrapped
// in a disclosed affiliate link -- plus a [figure] written on its own, outside any.

const ms = (value) => (value.endsWith('ms') ? parseFloat(value) : parseFloat(value) * 1000);

const slideshowOf = (alt) => cy.get(`img[alt="${alt}"]`).closest('.slideshow');

// What actually rotates is the slideshow's direct child, which is a [figure] frame when
// one is used and the bare image otherwise. Tests assert against the frame, not the picture,
// so they hold for both shapes.
const frameOf = (alt) =>
  cy.get(`img[alt="${alt}"]`).then(($img) => {
    const slideshow = $img[0].closest('.slideshow');
    let frame = $img[0];
    while (frame.parentElement !== slideshow) frame = frame.parentElement;
    // Wrapped as jQuery, so it behaves like anything else cy.get yields.
    return cy.wrap(Cypress.$(frame));
  });

const computed = ($el, property) => window.getComputedStyle($el[0])[property];

describe('[slideshow] shortcode', () => {
  beforeEach(() => {
    cy.visit('/blog/page/slideshow');
  });

  it('wraps the images it was given and counts them', () => {
    slideshowOf('rotating one')
      .should('have.attr', 'data-slides', '2')
      .find('img')
      .should('have.length', 2);
  });

  it('carries the interval the author asked for', () => {
    slideshowOf('rotating one').should(($el) => {
      expect(computed($el, 'getPropertyValue') && $el[0].style.getPropertyValue('--platzky-slideshow-interval').trim())
        .to.eq('4000ms');
    });
  });

  it('is styled by the shipped stylesheet, not by the markup', () => {
    // If blog.css were not loaded, or its data-slides selectors did not match what the
    // shortcode writes, every one of these would fall back to a static, opaque image and
    // the slideshow would silently be a stack of pictures.
    slideshowOf('rotating one').should(($el) => {
      expect(computed($el, 'position')).to.eq('relative');
    });
    frameOf('rotating one').should(($el) => {
      // The first frame stays in flow; it is what gives the slideshow its box.
      expect(computed($el, 'position')).to.eq('static');
    });
    frameOf('rotating two').should(($el) => {
      expect(computed($el, 'position')).to.eq('absolute');
    });
  });

  it('drives the animation from the interval', () => {
    // Two slides means each is shown for half the cycle, so the cycle is twice the
    // interval -- the calc() in the stylesheet reading the custom property the shortcode
    // wrote. 4000ms in, 8s out.
    frameOf('rotating one').should(($el) => {
      expect(computed($el, 'animationName')).to.eq('platzky-slideshow-2');
      expect(ms(computed($el, 'animationDuration'))).to.eq(8000);
      expect(ms(computed($el, 'animationDelay'))).to.eq(0);
    });
    frameOf('rotating two').should(($el) => {
      // Staggered by one interval, which is what puts the second slide on screen as the
      // first leaves rather than alongside it.
      expect(ms(computed($el, 'animationDelay'))).to.eq(4000);
    });
  });

  it('a second slideshow keeps its own interval', () => {
    // Two slideshows on one page: the interval is a custom property on each element, so a
    // second one must not inherit the first's. Only a second instance can show that.
    cy.get('img[alt="promo one"]').should(($el) => {
      expect(ms(computed($el, 'animationDuration'))).to.eq(4000);
    });
  });

  it('rotates bare images the same way it rotates figure frames', () => {
    // The affiliate slideshow is the page's only *animating* bare-image one, so it carries
    // the whole no-[figure] path: without this, converting the rotating slideshow to frames
    // would have left that form's stacking and geometry untested.
    slideshowOf('promo one').then(($el) => {
      const [first, second] = [...$el[0].children];
      expect(first.tagName, 'a bare image is its own frame').to.eq('IMG');
      expect(getComputedStyle(first).position).to.eq('static');
      expect(getComputedStyle(second).position).to.eq('absolute');

      const boxes = [first, second].map((f) => f.getBoundingClientRect());
      ['x', 'y', 'width', 'height'].forEach((side) => {
        expect(Math.round(boxes[1][side]), side).to.eq(Math.round(boxes[0][side]));
      });
    });
  });

  it('actually cross-fades from one slide to the next', () => {
    // The behaviour the whole feature is for, and the only assertion here that needs time
    // to pass: opacity is animated, so it can only be read from a running browser.
    frameOf('rotating one').should(($el) => {
      expect(Number(computed($el, 'opacity'))).to.be.greaterThan(0.8);
    });
    frameOf('rotating two').should(($el) => {
      expect(Number(computed($el, 'opacity'))).to.be.lessThan(0.2);
    });

    // Past the first slide's half of the 8s cycle, with room for the fade to finish.
    cy.wait(5000);

    frameOf('rotating one').should(($el) => {
      expect(Number(computed($el, 'opacity'))).to.be.lessThan(0.2);
    });
    frameOf('rotating two').should(($el) => {
      expect(Number(computed($el, 'opacity'))).to.be.greaterThan(0.8);
    });
  });

  it('shows every image when there are more than it can rotate', () => {
    // The failure this guards against is a missing CSS rule silently hiding an image
    // somebody wrote: the stacking and the animation are scoped to the counts the
    // stylesheet has timings for, so a fifth image leaves them all in normal flow.
    slideshowOf('many 1').should('have.attr', 'data-slides', '5').find('img').should('have.length', 5);

    ['many 1', 'many 3', 'many 5'].forEach((alt) => {
      cy.get(`img[alt="${alt}"]`).should(($el) => {
        expect(computed($el, 'position')).to.eq('static');
        expect(computed($el, 'animationName')).to.eq('none');
        expect(Number(computed($el, 'opacity'))).to.eq(1);
      });
    });
  });

  it('renders inside a link, disclosed as sponsored', () => {
    // The affiliate shape: one anchor around the whole slideshow. rel is unioned with what
    // target="_blank" already forces, never a replacement for it.
    cy.get('a[href="https://example.com/deal"]')
      .should('have.attr', 'target', '_blank')
      .and(($el) => {
        const rel = $el.attr('rel').split(/\s+/);
        expect(rel).to.include.members(['sponsored', 'noopener', 'noreferrer']);
      })
      .find('.slideshow img')
      .should('have.length', 2);
  });

  it('lands every rotating slide on exactly the same box', () => {
    // The bug no other assertion here can see: a slide can be correctly `position:
    // absolute` and still be positioned against the wrong containing block, so the
    // pictures end up side by side rather than on top of each other. Only geometry
    // catches that, and it caught it twice while this was being built.
    slideshowOf('rotating one').then(($el) => {
      $el[0].querySelectorAll('img').forEach((img) => {
        expect(img.complete && img.naturalWidth > 0, `${img.alt} loaded`).to.be.true;
      });
      const [first, second] = [...$el[0].children].map((f) => f.getBoundingClientRect());
      ['x', 'y', 'width', 'height'].forEach((side) => {
        expect(Math.round(second[side]), side).to.eq(Math.round(first[side]));
      });
    });
  });

  it('leaves an unrotatable slideshow as a vertical sequence', () => {
    // The other half of the same property: images the stylesheet cannot rotate must stay
    // in normal flow, each below the last, rather than being stacked and hidden.
    slideshowOf('many 1').then(($el) => {
      const tops = [...$el[0].querySelectorAll('img')].map((img) => img.getBoundingClientRect().y);
      tops.slice(1).forEach((top, i) => expect(top).to.be.greaterThan(tops[i]));
    });
  });

  it('puts a figure’s text beside its picture, not under it', () => {
    // A [figure] exists so a caption can travel with its image. Measured rather than
    // asserted on the CSS, because "beside" is a fact about where the text ended up.
    cy.get('img[alt="rotating one"]').then(($img) => {
      const figure = $img[0].closest('.platzky-figure');
      const picture = $img[0].getBoundingClientRect();
      const range = document.createRange();
      range.selectNodeContents(figure);
      // Text starts to the right of the picture and overlaps it vertically.
      const words = [...figure.childNodes]
        .filter((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim())
        .map((n) => {
          const r = document.createRange();
          r.selectNodeContents(n);
          return r.getBoundingClientRect();
        });
      expect(words.length, 'figure has text of its own').to.be.greaterThan(0);
      expect(words[0].left).to.be.greaterThan(picture.right - 1);
      expect(words[0].top).to.be.lessThan(picture.bottom);
    });
  });

  it('keeps a caption as one run of prose', () => {
    // Regression test: the figure was briefly a flex container, which made every text node
    // and inline element its own flex item. The fixture's red_letter plugin wraps each "a"
    // in a span, so "chapter" rendered as "ch a pter" with a gap either side, and any
    // caption containing a link would have broken the same way.
    cy.get('img[alt="rotating one"]').then(($img) => {
      const figure = $img[0].closest('.platzky-figure');
      expect(getComputedStyle(figure).display).to.not.eq('flex');
      // The pieces of the word abut: no gap is inserted between a text node and the span
      // that interrupts it.
      const pieces = [...figure.childNodes].filter(
        (n) => n.nodeType === Node.TEXT_NODE || n.nodeName === 'SPAN'
      );
      const rects = pieces.map((n) => {
        const r = document.createRange();
        r.selectNodeContents(n);
        return r.getBoundingClientRect();
      });
      rects.slice(1).forEach((rect, i) => {
        expect(rect.left - rects[i].right, 'gap between caption pieces').to.be.lessThan(2);
      });
    });
  });

  it('lays out a figure written on its own, outside any slideshow', () => {
    // A picture with its text beside it is worth having without a rotation, and writing a
    // slideshow of one to get it would be nonsense. Before the layout was unscoped from
    // .slideshow this rendered as an unstyled div: image on its own line, text under it.
    cy.get('img[alt="lone figure"]').then(($img) => {
      const figure = $img[0].closest('.platzky-figure');
      expect(figure.closest('.slideshow'), 'is outside any slideshow').to.be.null;
      expect(getComputedStyle(figure).display).to.eq('flow-root');
      expect(getComputedStyle($img[0]).float).to.eq('left');

      const picture = $img[0].getBoundingClientRect();
      const text = [...figure.childNodes]
        .filter((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim())
        .map((n) => {
          const r = document.createRange();
          r.selectNodeContents(n);
          return r.getBoundingClientRect();
        })[0];
      expect(text.left).to.be.greaterThan(picture.right - 1);
      expect(text.top).to.be.lessThan(picture.bottom);
    });
  });

  it('lets the page style its figures', () => {
    // blog.css invites a site to override .platzky-figure, and the fixture page does it
    // from its own `css` field. Each frame gets its own background, which is also what
    // makes the cross-fade legible in a screenshot when two book covers look alike.
    const backgrounds = [];
    ['rotating one', 'rotating two'].forEach((alt) => {
      cy.get(`img[alt="${alt}"]`).then(($img) => {
        const style = getComputedStyle($img[0].closest('.platzky-figure'));
        expect(style.backgroundColor, `${alt} background`).to.not.eq('rgba(0, 0, 0, 0)');
        expect(parseFloat(style.paddingLeft), `${alt} padding`).to.be.greaterThan(0);
        backgrounds.push(style.backgroundColor);
      });
    });
    cy.then(() => {
      // Per-frame, not one rule for all of them.
      expect(backgrounds[0]).to.not.eq(backgrounds[1]);
    });
  });

  it('spans the page when asked to, and still stacks its frames', () => {
    // width="full" breaks out of the centred content column, so the test is against the
    // viewport rather than the parent. The frames must still land on each other, which a
    // wider container is exactly what would break.
    slideshowOf('rotating one').then(($el) => {
      const slideshow = $el[0];
      expect(slideshow.getAttribute('data-width')).to.eq('full');

      expect(slideshow.getBoundingClientRect().width, 'spans the viewport')
        .to.be.closeTo(Cypress.config('viewportWidth'), 2);
      expect(slideshow.getBoundingClientRect().width, 'wider than the column it sits in')
        .to.be.greaterThan(slideshow.parentElement.getBoundingClientRect().width);

      const [first, second] = [...slideshow.children].map((f) => f.getBoundingClientRect());
      ['x', 'y', 'width', 'height'].forEach((side) => {
        expect(Math.round(second[side]), side).to.eq(Math.round(first[side]));
      });
    });
  });

  it('breaks out without making the page scroll sideways', () => {
    // The classic way a full-bleed element goes wrong: 100vw counts the scrollbar, so the
    // element overhangs and the whole page gains a horizontal scrollbar. The negative
    // margins avoid vw for the width, and this is what keeps it that way.
    cy.document().then((doc) => {
      expect(doc.documentElement.scrollWidth)
        .to.be.at.most(Cypress.config('viewportWidth') + 1);
    });
  });

  it('leaves a slideshow that did not ask for it fitting its frames', () => {
    // Shrink-wrapping is what "fit" means, so assert it directly: the container is exactly
    // as wide as the frame inside it. Comparing against the parent would not work here —
    // this slideshow's parent is the affiliate <a>, and an inline box reports no width.
    slideshowOf('promo one').then(($el) => {
      const slideshow = $el[0];
      expect(slideshow.getAttribute('data-width')).to.eq('fit');
      const frame = slideshow.children[0].getBoundingClientRect();
      expect(slideshow.getBoundingClientRect().width, 'hugs its frame')
        .to.be.closeTo(frame.width, 1);
    });
  });
});
