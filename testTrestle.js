require('dotenv').config();
const { lookupAddress } = require('./trestleService');

async function main() {
  const results = await lookupAddress({
    street: '1600 Pennsylvania Ave NW',
    city: 'Washington',
    state: 'DC',
    zip: '20500'
  });

  if (!results) {
    console.log('\nLookup failed. Check errors above.');
    return;
  }

  if (results.length === 0) {
    console.log('\nNo results returned.');
    return;
  }

  const show = results.slice(0, 5);
  console.log(`\nFound ${results.length} resident(s), showing first ${show.length}:\n`);

  show.forEach((person, i) => {
    console.log(`--- Resident ${i + 1} ---`);
    console.log(`  Name:   ${person.name || 'N/A'}`);

    if (person.phones.length > 0) {
      person.phones.forEach(p => {
        console.log(`  Phone:  ${p.number} (${p.type})`);
      });
    } else {
      console.log('  Phone:  None found');
    }

    if (person.emails.length > 0) {
      person.emails.forEach(e => {
        console.log(`  Email:  ${e}`);
      });
    } else {
      console.log('  Email:  None found');
    }

    console.log('');
  });
}

main();
