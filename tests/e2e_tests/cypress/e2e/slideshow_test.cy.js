// The [slideshow] shortcode's rotation is pure CSS, living in static/blog.css rather than
// in the markup the shortcode returns. Unit tests can only see that markup, so everything
// that decides whether the thing actually rotates -- that the stylesheet is loaded, that
// its data-slides selectors match, that the interval custom property survives calc() -- is
// only observable in a browser. That is what this file is for.
//
// The test data has a page with three slideshows: one rotating pair, one with more images
// than the stylesheet has timings for, and one wrapped in a disclosed affiliate link.

const ms = (value) => (value.endsWith('ms') ? parseFloat(value) : parseFloat(value) * 1000);

const slideshowOf = (alt) => cy.get(`img[alt="${alt}"]`).closest('.slideshow');

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
    cy.get('img[alt="rotating one"]').should(($el) => {
      expect(computed($el, 'position')).to.eq('static');
    });
    cy.get('img[alt="rotating two"]').should(($el) => {
      expect(computed($el, 'position')).to.eq('absolute');
    });
  });

  it('drives the animation from the interval', () => {
    // Two slides means each is shown for half the cycle, so the cycle is twice the
    // interval -- the calc() in the stylesheet reading the custom property the shortcode
    // wrote. 4000ms in, 8s out.
    cy.get('img[alt="rotating one"]').should(($el) => {
      expect(computed($el, 'animationName')).to.eq('platzky-slideshow-2');
      expect(ms(computed($el, 'animationDuration'))).to.eq(8000);
      expect(ms(computed($el, 'animationDelay'))).to.eq(0);
    });
    cy.get('img[alt="rotating two"]').should(($el) => {
      // Staggered by one interval, which is what puts the second slide on screen as the
      // first leaves rather than alongside it.
      expect(ms(computed($el, 'animationDelay'))).to.eq(4000);
    });
  });

  it('a second slideshow keeps its own interval', () => {
    cy.get('img[alt="promo one"]').should(($el) => {
      expect(ms(computed($el, 'animationDuration'))).to.eq(4000);
    });
  });

  it('actually cross-fades from one slide to the next', () => {
    // The behaviour the whole feature is for, and the only assertion here that needs time
    // to pass: opacity is animated, so it can only be read from a running browser.
    cy.get('img[alt="rotating one"]').should(($el) => {
      expect(Number(computed($el, 'opacity'))).to.be.greaterThan(0.8);
    });
    cy.get('img[alt="rotating two"]').should(($el) => {
      expect(Number(computed($el, 'opacity'))).to.be.lessThan(0.2);
    });

    // Past the first slide's half of the 8s cycle, with room for the fade to finish.
    cy.wait(5000);

    cy.get('img[alt="rotating one"]').should(($el) => {
      expect(Number(computed($el, 'opacity'))).to.be.lessThan(0.2);
    });
    cy.get('img[alt="rotating two"]').should(($el) => {
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
      const slides = [...$el[0].querySelectorAll('img')];
      slides.forEach((img) => {
        expect(img.complete && img.naturalWidth > 0, `${img.alt} loaded`).to.be.true;
      });
      const [first, second] = slides.map((img) => img.getBoundingClientRect());
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
});
