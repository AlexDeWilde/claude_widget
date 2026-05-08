20260415 changed from 100-used to just USED: 
	In background.js, find this section and make one small change:
	Current code (around line 40):
	javascriptlet used = parseInt(pMatch[1]);
	percentage = (100 - used).toString();
	Change to:
	javascriptpercentage = pMatch[1];
	That's it — just remove the (100 - used) inversion and pass the raw scraped value through directly. 
	
