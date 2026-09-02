// STRIP_CONTENT_HTML is on in e2e_test_config.yml. The test data has a page whose
// content mixes HTML written in prose with HTML written inside a [html] block, plus
// an [image] shortcode.
describe('STRIP_CONTENT_HTML', () => {
  beforeEach(() => {
    cy.visit('/blog/page/strip-html');
  });

  it('removes HTML written in prose, keeping the text it wrapped', () => {
    cy.get('.post-content').contains('bold text');
    cy.get('.post-content b').should('not.exist');
    cy.get('#stripped-image').should('not.exist');
  });

  it('keeps HTML written inside [html], as HTML', () => {
    // [html] is verbatim, so it is how an author marks a piece of HTML they mean on a
    // site that strips the rest — the tag survives as a real element.
    cy.get('#kept-image')
      .should('exist')
      .and('have.attr', 'src', '/static/img/none.png');
  });

  it('does not wrap what [html] passes through', () => {
    cy.get('.post-content pre').should('not.exist');
    cy.get('.post-content code').should('not.exist');
  });

  it('still renders a shortcode, which is what replaces the stripped HTML', () => {
    // [image] is the formatting an author gets instead of writing <img> by hand, so the
    // flag must not disable it — square brackets are nothing to an HTML parser.
    cy.get('.post-content img[alt="shortcode image"]')
      .should('have.attr', 'src', '/static/img/none.png');
  });

  it('leaves exactly the two images that were meant', () => {
    // The one [html] passed through and the one [image] rendered; the prose <img> is gone.
    cy.get('.post-content img').should('have.length', 2);
  });
});
