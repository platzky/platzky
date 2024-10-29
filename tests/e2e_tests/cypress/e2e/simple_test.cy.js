function posts() {
  return cy.get('.row.align-items-center')
}

describe('Blog test', () => {
  beforeEach(() => {
    cy.visit('/blog');
  });

  it('display posts and leave comment in one of them', () => {
    posts()
      .should('have.length', 2)
      .first()
      .within( () => {
        cy.get('img')
          .should('have.attr', 'alt', 'alternate text')
        }
      )
      .contains('title').click()
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
    cy.contains('No such page')
  })

// TODO add tests:
//   - post and page without image
//   - translations
//

})
