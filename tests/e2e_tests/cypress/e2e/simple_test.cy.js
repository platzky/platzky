function posts() {
  return cy.get('.row.align-items-center')
}

describe('Blog test', () => {
  beforeEach(() => {
    cy.visit('/blog');
  });

  it('display posts and leave comment in one of them', () => {
    posts().should('have.length', 3)
    cy.contains('.post-title', 'title')
      .closest('.row.align-items-center')
      .within(() => {
        cy.get('img').should('have.attr', 'alt', 'alternate text')
        cy.contains('title').click()
      })
    cy.contains('content')

    let user = 'commenting user'
    let comment = 'comment content'

    cy.get('#author_name').type(user)
    cy.get('#comment').type(comment)
    cy.get('#submit').click()

    cy.get('.table.table-striped')
      .contains(user)
    cy.get('.table.table-striped')
      .contains(comment)
  })



  it('clicking tag it filters posts with tag', () => {
    cy.get('.post-meta').contains('tag/3').click()
    cy.get('.post-title').should('have.length', 1)
  })

  it('return 404 on nonexisting page', () => {
    const url404test = '/page/non-existing-page'
    cy.request({url: url404test, failOnStatusCode: false})
      .then(resp=> expect(resp.status).to.eq(404))

    cy.visit(url404test, {failOnStatusCode: false})
    cy.contains("This page doesn't exist")
  })

  it('loads page with minimal fields (no comments, tags, language, date)', () => {
    // This is a regression test for a bug where pages required all Post fields
    // (comments, tags, language, date) even though they should be optional.
    // The test data has pages without these optional fields.
    cy.visit('/blog/page/page')
    cy.contains('page title')
    cy.contains('page content')
  })

  it('500s a page whose css tries to break out of its <style> tag', () => {
    // The test data has a page whose css field is
    // "</style><script>alert('xss')</script><style>" — the trailing <style>
    // is part of the attack: it would make the page look visually unchanged
    // even if the breakout worked. Model validation rejects this css outright,
    // so the page 500s rather than rendering a live <script> tag.
    const url = '/blog/page/style-breakout'
    cy.on('window:alert', () => {
      throw new Error('script from css breakout executed')
    })

    cy.request({url: url, failOnStatusCode: false})
      .then(resp => expect(resp.status).to.eq(500))

    cy.visit(url, {failOnStatusCode: false})
    cy.contains("This page doesn't exist")
  })

// TODO add tests:
//   - post and page without image
//

})
