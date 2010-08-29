# sitelib for noarch packages, sitearch for others (remove the unneeded one)
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}

Name:           pulp
Version:        0.0.58
Release:        1%{?dist}
Summary:        An application for managing software content

Group:          Development/Languages
License:        GPLv2
URL:            https://fedorahosted.org/pulp/
Source0:        %{name}-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch:      noarch
BuildRequires:  python2-devel
BuildRequires:  python-setuptools
BuildRequires:  python-nose	
BuildRequires:  rpm-python

Requires: pulp-common
Requires: python-pymongo
Requires: python-setuptools
Requires: python-webpy
Requires: python-simplejson
Requires: grinder
Requires: httpd
Requires: mod_wsgi
Requires: mod_python
Requires: mod_ssl
Requires: mongo
Requires: mongo-server
Requires: m2crypto
Requires: openssl
Requires: %{name}-client

%if 0%{?rhel} > 5
Requires: python-hashlib
%endif


%description
Pulp provides replication, access, and accounting for software repositories.


%package common
Summary:        Pulp common modules.
Group:          Development/Languages
BuildRequires:  rpm-python
Requires: python-simplejson
Requires: python-qpid >= 0.7

%description common
Contains modules common to the Pulp server and client.


%package client
Summary:        Client side tools for managing content on pulp server
Group:          Development/Languages
BuildRequires:  rpm-python
Requires: pulp-common
Requires: python-simplejson
Requires: m2crypto

%if 0%{?rhel} > 5
Requires: python-hashlib
%endif

%description client
A collection of tools to interact and perform content specific operations such as repo management, 
package profile updates etc.
 

%prep
%setup -q

%build
pushd src
%{__python} setup.py build
popd

%install
rm -rf %{buildroot}
pushd src
%{__python} setup.py install -O1 --skip-build --root %{buildroot}
popd

# Pulp Configuration
mkdir -p %{buildroot}/etc/pulp
cp etc/pulp/* %{buildroot}/etc/pulp

mkdir -p %{buildroot}/var/log/pulp

# Apache Configuration
mkdir -p %{buildroot}/etc/httpd/conf.d/
cp etc/httpd/conf.d/pulp.conf %{buildroot}/etc/httpd/conf.d/

cp -R srv %{buildroot}

mkdir -p %{buildroot}/etc/pki/pulp
mkdir -p %{buildroot}/etc/pki/consumer
cp etc/pki/pulp/* %{buildroot}/etc/pki/pulp

mkdir -p %{buildroot}/etc/pki/content

mkdir -p %{buildroot}/var/lib/pulp
mkdir -p %{buildroot}/var/www
ln -s /var/lib/pulp %{buildroot}/var/www/pub

# Pulp Agent
mkdir -p %{buildroot}/usr/bin
cp bin/pulpd %{buildroot}/usr/bin

mkdir -p %{buildroot}/etc/init.d
cp etc/init.d/pulpd %{buildroot}/etc/init.d

# Remove egg info
rm -rf %{buildroot}/%{python_sitelib}/%{name}*.egg-info

%clean
rm -rf %{buildroot}

%post
setfacl -m u:apache:rwx /etc/pki/content/

%files
%defattr(-,root,root,-)
%doc
# For noarch packages: sitelib
%{python_sitelib}/pulp/server/
%config(noreplace) /etc/pulp/pulp.conf
%config(noreplace) /etc/httpd/conf.d/pulp.conf
%attr(775, apache, apache) /etc/pulp
%attr(750, apache, apache) /srv/pulp/webservices.wsgi
%attr(3775, apache, apache) /var/lib/pulp
%attr(3775, apache, apache) /var/www/pub
%attr(3775, apache, apache) /var/log/pulp
%attr(3775, root, root) /etc/pki/content
/etc/pki/pulp/ca.key
/etc/pki/pulp/ca.crt


%files common
%defattr(-,root,root,-)
%doc
%{python_sitelib}/pulp/*.py*
%{python_sitelib}/pulp/messaging/


%files client
%defattr(-,root,root,-)
%doc
# For noarch packages: sitelib
%{python_sitelib}/pulp/client/
%{_bindir}/pulp-admin
%{_bindir}/pulp-client
%{_bindir}/pulpd
%attr(755,root,root) %{_sysconfdir}/init.d/pulpd
%attr(755,root,root) %{_sysconfdir}/pki/consumer/
%config(noreplace) /etc/pulp/client.conf

%post client
chkconfig --add pulpd

%preun client
if [ $1 = 0 ] ; then
   /sbin/service pulpd stop >/dev/null 2>&1
   /sbin/chkconfig --del pulpd
fi


%changelog
* Fri Aug 27 2010 Jay Dobies <jason.dobies@redhat.com> 0.0.58-1
- Make sure to include the user's home directory in the destination
  (jason.dobies@redhat.com)
- Added hook to use the admin certificate if one is found.
  (jason.dobies@redhat.com)
- Fix the consumer help to list usage correctly (pkilambi@redhat.com)
- Merge branch 'master' of git+ssh://git.fedorahosted.org/git/pulp
  (pkilambi@redhat.com)
- fixing regression where we add list instead of str to install list of there
  is no arch (pkilambi@redhat.com)
- Added CLI hooks for admin login/logout. (jason.dobies@redhat.com)
- Refactored so we have access to the user object to store as the principal if
  the user is authenticated. (jason.dobies@redhat.com)
- Merge branch 'master' of ssh://git.fedorahosted.org/git/pulp
  (jconnor@redhat.com)
- implemented progress callbacks for rhn and yum repo syncs this includes a
  "pass-through" callback in tasks, that take a callback argument name and the
  callback function then passes in its own callback wrapper which executes the
  callback and assigns it to a progress field added callback parameters to all
  repo sync methods modified jmathews callback to return a dictionary
  (jconnor@redhat.com)
- Added webservice calls for admin auth certificates (jason.dobies@redhat.com)
- Added API for retrieving an admin certificate for the currently logged in
  user (jason.dobies@redhat.com)
- Merge config writes to alt config when specified. (jortel@redhat.com)
- Renamed to reflect it's an API test (jason.dobies@redhat.com)
- Added return type docs (jason.dobies@redhat.com)
- Removed plain text echo of the user's password (jason.dobies@redhat.com)
- Merge branch 'master' of ssh://git.fedorahosted.org/git/pulp
  (jconnor@redhat.com)
- Revert "Reverting cancel sync change to check whether this commit cause json
  errors" Confirmed that JSON errors were not because of this commit This
  reverts commit 983791a517a85dd84b4df7197eef207b7e100489.
  (skarmark@redhat.com)
- Reverting cancel sync change to check whether this commit cause json errors
  (skarmark@redhat.com)
- Not printing task id at the time of sync (skarmark@redhat.com)
- Adding cancel sync and sync status to cli (skarmark@redhat.com)
- shortten environment var. (jortel@redhat.com)
- Add certlib (work in progress) (jortel@redhat.com)
- Default key and cert. (jortel@redhat.com)
- Add PULP_CLIENT_ALTCONF envrionment var to specify alt conf to be merged.
  (jortel@redhat.com)
- changing client.conf to point to localhost and not guardian
  (skarmark@redhat.com)
- repo sync timeout changes (skarmark@redhat.com)
- repo sync timeout changes (skarmark@redhat.com)
- adding productid identifier as an optional reference to tie candlepin product
  to repos (pkilambi@redhat.com)
- some re-organization (jconnor@redhat.com)

* Wed Aug 25 2010 Jay Dobies <jason.dobies@redhat.com> 0.0.57-1
- Missed an entry in the package refactor (jason.dobies@redhat.com)

* Wed Aug 25 2010 Mike McCune <mmccune@redhat.com> 0.0.56-1
- rebuild
* Wed Aug 25 2010 Jay Dobies <jason.dobies@redhat.com> 0.0.55-1
- Release 0.1 build
* Fri Aug 20 2010 Mike McCune <mmccune@redhat.com> 0.0.54-1
- rebuild
* Fri Aug 20 2010 Jay Dobies <jason.dobies@redhat.com> 0.0.53-1
- Missed a server import rename (jason.dobies@redhat.com)
- Merge branch 'master' into code-reorganization (jason.dobies@redhat.com)
- Discontinue installing the egg into site-packages. (jortel@redhat.com)
- Fix .spec problem with pulp-* egg. (jortel@redhat.com)
- Update spec to match code refactoring. (jortel@redhat.com)
- Update spec to match code refactoring. (jortel@redhat.com)
- Update imports for refactoring. (jortel@redhat.com)
- Updated for new package structure and cleaned up unused imports
  (jason.dobies@redhat.com)
- Updated imports for new structure (jason.dobies@redhat.com)
- quiet the logging (mmccune@redhat.com)
- Move pulptools to: pulp.client.  Update pmf imports. (jortel@redhat.com)
- update section names pmf->messaging. (jortel@redhat.com)
- moved to server where it belongs.  Updated imports and .conf section.
  (jortel@redhat.com)
- moved pmf to: pulp.messaging. (jortel@redhat.com)
- First steps in major package refactoring: just shuffling files into the
  proper directories (jason.dobies@redhat.com)
- added unicode cast to principal (jconnor@redhat.com)
- reset does not need to manage a queue managed resource (jconnor@redhat.com)
- check if packages exist before computing the length (pkilambi@redhat.com)
- set the exception to jus message instead of an object so its serializable
  (pkilambi@redhat.com)
- removing bad attributes on Task objects causing tracebacks
  (pkilambi@redhat.com)

* Wed Aug 18 2010 Mike McCune <mmccune@redhat.com> 0.0.52-1
- rebuild

* Mon Aug 16 2010 Jeff Ortel <jortel@redhat.com> 0.0.50-1
- rebuild
* Thu Aug 12 2010 Mike McCune <mmccune@redhat.com> 0.0.49-1
- rebuild
* Fri Aug 06 2010 Mike McCune <mmccune@redhat.com> 0.0.48-1
- rebuild

* Wed Aug 04 2010 Mike McCune <mmccune@redhat.com> 0.0.47-1
- rebuild
* Fri Jul 30 2010 Mike McCune <mmccune@redhat.com> 0.0.46-1
- rebuild
* Thu Jul 29 2010 Mike McCune <mmccune@redhat.com> 0.0.44-1
- rebuild

* Tue Jul 27 2010 Jason L Connor <jconnor@redhat.com> 0.0.43-1
- tio tag
* Tue Jul 27 2010 Jason L Connoe <jconnor@redhat.com> 0.0.42-1
- added gid and sticky bit to /var/[lib,log,www]/pulp directories

* Fri Jul 23 2010 Mike McCune <mmccune@redhat.com> 0.0.41-1
- rebuild
* Thu Jul 22 2010 Jason L Connor <jconnor@redhat.com> 0.0.40-1
- removed juicer from configuration

* Fri Jul 16 2010 Mike McCune <mmccune@redhat.com> 0.0.39-1
- rebuild
* Thu Jul 15 2010 Sayli Karmarkar <skarmark@redhat.com> 0.0.37-1
- Turned off client side SSL cert checking (jason.dobies@redhat.com)
- changed string index to find so that the logic will work (jconnor@redhat.com)
- added auditing to users api (jconnor@redhat.com)
- added spec and fields to users api some code clean up added check for neither
  id or certificate in create (jconnor@redhat.com)
- added auditing to packages api (jconnor@redhat.com)
- added auditing to consumer api (jconnor@redhat.com)
- added auditing to the repo api (jconnor@redhat.com)
- fixed bug in copy that doesnt return a list (jconnor@redhat.com)
- finished general code review and cleanup added _get_existing_repo to
  standardize exception message and reduce cut-copy-paste code
  (jconnor@redhat.com)

* Thu Jul 15 2010 Mike McCune <mmccune@redhat.com> 0.0.36-1
- rebuild
* Thu Jul 01 2010 Mike McCune <mmccune@redhat.com> 0.0.35-1
- rebuild

* Thu Jul 01 2010 Jay Dobies <jason.dobies@redhat.com> 0.0.34-1
- Removed unncessary line; ownership of /var/log/pulp is given to apache in
  %post (jason.dobies@redhat.com)

* Wed Jun 30 2010 Mike McCune <mmccune@redhat.com> 0.0.33-1
- rebuild
* Mon Jun 28 2010 Mike McCune <mmccune@redhat.com> 0.0.31-1
- rebuild
* Wed Jun 23 2010 Mike McCune <mmccune@redhat.com> 0.0.28-1
- rebuild
* Mon Jun 21 2010 Mike McCune <mmccune@redhat.com> 0.0.26-1
- Weekly rebuild.  See SCM for history

* Wed Jun 16 2010 Mike McCune <mmccune@redhat.com> 0.0.24-1
- massive amounts of changes from the last few weeks

* Wed Jun 09 2010 Pradeep Kilambi <pkilambi@redhat.com> 0.0.23-1
- inlcude only pulp and juicer for pulp rpm (pkilambi@redhat.com)
- Adding pulp-tools as a new subrpm (pkilambi@redhat.com)
- Change pythonpath to new client location. (jortel@redhat.com)
- Fix test_consumerwithpackage() in WS unit tests. Add
  juicer/controllers/base.py.params() to get passed parameters.
  (jortel@redhat.com)
- rename client to pulp-tools (pkilambi@redhat.com)
- removing accidental log entry (pkilambi@redhat.com)
- moving client under src for packaging (pkilambi@prad.rdu.redhat.com)
- Add consumer update() in WS. (jortel@redhat.com)
- Assign model object._id in constructor. (jortel@redhat.com)
- Another dumb mistake (jason.dobies@redhat.com)
- Fat fingered the signature (jason.dobies@redhat.com)
- streamline bind/unbind params. (jortel@redhat.com)
- Client side web service implementation for packages (jason.dobies@redhat.com)
- switching to an insert vs append so we always use src in git tree
  (mmccune@redhat.com)
- Add basic web service API tests. (jortel@redhat.com)
- Typo (jason.dobies@redhat.com)
- Initial work on packages API (jason.dobies@redhat.com)
- Added web service hook to consumer clean (jason.dobies@redhat.com)
- Added web service hook to repository clean (jason.dobies@redhat.com)
- Cleaned up for PEP8 format (jason.dobies@redhat.com)
- Cleaning up for PEP8 format (jason.dobies@redhat.com)
- Cleaning up for PEP8 format (jason.dobies@redhat.com)
- Cleaning up for PEP8 format (jason.dobies@redhat.com)
- Fixed broken config test (jason.dobies@redhat.com)
- Docs (jason.dobies@redhat.com)
- Oops, forgot to remove debug info (jason.dobies@redhat.com)
- Fixed logic for importing packages to make sure the package version doesn't
  already exist (jason.dobies@redhat.com)
- Moved non-unit test to common area (jason.dobies@redhat.com)
- Removed unsupported test file (jason.dobies@redhat.com)
- the proxy call's signature matches api (pkilambi@redhat.com)
- Added test case for RHN sync (jason.dobies@redhat.com)

* Wed Jun 09 2010 Pradeep Kilambi <pkilambi@redhat.com>
- Adding pulp-tools as a sub rpm to pulp

* Mon Jun 07 2010 Mike McCune <mmccune@redhat.com> 0.0.22-1
- Renamed method (jason.dobies@redhat.com)
- Refactored out common test utilities (jason.dobies@redhat.com)
- Removed temporary logging message (jason.dobies@redhat.com)

* Mon Jun 07 2010 Pradeep Kilambi <pkilambi@redhat.com> 0.0.20-1
- reflect the subscribed repos in list (pkilambi@redhat.com)
- Adding bind and unbind support for the cli (pkilambi@redhat.com)
- If repo dir doesnt exist create it before storing the file and adding some
  logging (pkilambi@redhat.com)

* Fri Jun 04 2010 Mike McCune <mmccune@redhat.com> 0.0.18-1
- rebuild
* Thu Jun 03 2010 Mike McCune <mmccune@redhat.com> 0.0.10-1
- large numbers of changes.  see git for list
* Thu Jun 03 2010 Jay Dobies <jason.dobies@redhat.com> 0.0.7-1
- Link the grinder synchronized packages over to apache
  (jason.dobies@redhat.com)
- was missing an import, and CompsException needed to be fully qualified
  (jmatthew@redhat.com)
- make the imports absolute to the files running
  (mmccune@gibson.pdx.redhat.com)
- added pulps configuration to wsgi script (jconnor@redhat.com)
- changed the way juicer handles pulp's configuration at runtime
  (jconnor@redhat.com)
- added preliminary packages controllers cleanup in repositories and consumers
  controllers (jconnor@redhat.com)
- removing failed test (mmccune@gibson.pdx.redhat.com)
- fixing the help options to render based on the command (pkilambi@redhat.com)
- Adding consumer commands and actions to corkscrew (pkilambi@redhat.com)
- debugging and testing of pulp rpm spec for new apache deployment
  (jconnor@redhat.com)
- removing gevet daemon deployment and adding apache deployment
  (jconnor@redhat.com)
- moving the POST to consumers call (pkilambi@redhat.com)
- Adding webservices consumer calls based on available api.
  (pkilambi@redhat.com)
- pkg counts in cli reports and adding consumer connections
  (pkilambi@redhat.com)
- Temporary configuration loading (jason.dobies@redhat.com)

* Wed Jun 02 2010 Jason L Connor <jconnor@redhat.com> 0.0.6-1
- removed gevent deployment
- added apache deployment

* Thu May 27 2010 Adam Young <ayoung@redhat.com> 0.0.5-1
- Updated Dirs in var (ayoung@redhat.com)
- Added a patch to build 32 bit on 64 bit RH systems (ayoung@redhat.com)
- Updated to the WsRepoApi (jason.dobies@redhat.com)
- First pass at web services tests (jason.dobies@redhat.com)
- Renamed RepoConnection methods to be the same as their RepoApi counterpart.
  This way, we can use the RepoConnection object as a web services proxy and
  pass it into the unit tests that make direct calls on the RepoApi object.
  (jason.dobies@redhat.com)
- moving sub calls to separate class (pkilambi@redhat.com)
- fixed typo in doc added id to repo_data for update (jconnor@redhat.com)
- spec file changes to get closer to Fedora compliance. (ayoung@redhat.com)
- Merge branch 'master' of ssh://git.fedorahosted.org/git/pulp
  (jason.dobies@redhat.com)
- Missing self reference (jason.dobies@redhat.com)
- added some task cleanup to tasks as well as the base queue class added
  cleanup calls to test_tasks (jconnor@redhat.com)
- fixed missing 'id' parameter to repository update (jconnor@redhat.com)
-  New project for pulp client. Initial commit includes: (pkilambi@redhat.com)
- removing authors (mmccune@redhat.com)
- minor cleanup (mmccune@redhat.com)
- fixed my regular expressions for repositories and test applications changed
  create repo from /repostiories/new/ to just /repositories/ in case someone
  wants a repo called 'new' updated doc to reflect change (jconnor@redhat.com)
- updated docs to reflect new id (jconnor@redhat.com)
- changing regex to accept any type of id (jconnor@redhat.com)
- added creat url to documentation (jconnor@redhat.com)
- added 'next' keyword some formatting cleanup (jconnor@redhat.com)
- create index in background and add more data to PackageGroup objects
  (jmatthew@redhat.com)
- deleting grinder.  now avail in its own git repo (mmccune@redhat.com)
- cleanup on setup and teardown (mmccune@redhat.com)
- Added grinder egg to ignore (jason.dobies@redhat.com)
- Refactored unit tests into their own directory (jason.dobies@redhat.com)
- add methods for listing package groups/categories from repo api
  (jmatthew@redhat.com)
- fixing randomString casing and making unit tests work without root
  (mmccune@redhat.com)
- adding the pulp repo file (jconnor@redhat.com)
- fixed my test_tasks for the fifo tests (jconnor@redhat.com)
- extensive regex construction for at time specifications added some
  documentation to at queues added place-holder persistent queue module
  (jconnor@redhat.com)
- Test update to see if I can commit (jason.dobies@redhat.com)
- adding object/api for PackageGroup and PackageGroupCategory to represent data
  in comps.xml (repodata). (jmatthew@redhat.com)
- mid-stream modifications of more powerful at time spec parser
  (jconnor@redhat.com)
- adding preuninstall to stop a currently running server adding forceful
  deletion of db lock to uninstall (jconnor@redhat.com)
- added user and group cleanup on uninstall to mongo's spec file
  (jconnor@redhat.com)

* Mon May 24 2010 Adam Young <ayoung@redhat.com> 0.0.4-1
- added dep for  setup-tools (ayoung@redhat.com)
- Removed the _U option that was breaking installs on epel. (ayoung@redhat.com)
- Removed build dep on pymongo, as it breaks a mock build. (ayoung@redhat.com)
- Added nosetest, with failing tests excluded. (ayoung@redhat.com)
- Corrected name in changelog (ayoung@redhat.com)
- Updated changelog. (ayoung@redhat.com)
- Updated to work with tito. (ayoung@redhat.com)
- Adding objects for PackageGroup & Category (jmatthew@redhat.com)
- removed duplicate 'consumers' definiton in ConsumerApi (jmatthew@redhat.com)
- adding unique index on all objects based on id (mmccune@redhat.com)
- pointing readme to wiki (mmccune@redhat.com)
- validate downloaded bits before status checks . this way we can clean up
  empty packages and the return error state (pkilambi@redhat.com)
- remove uneeded dir find code.  instead use magic __file__ attrib
  (mmccune@redhat.com)
- make it so we can run our tests from top level of project
  (mmccune@redhat.com)
- Automatic commit of package [grinder] release [0.0.49-1].
  (jmatthew@redhat.com)
- fix 'fetch' call to pass in hashType, this prob showed up during a long sync
  when auth data became stale we would refresh auth data, then re-call fetch.
  The call to fetch was missing hashType (jmatthew@redhat.com)
- Automatic commit of package [pulp] release [0.0.3-1]. (ayoung@redhat.com)
- adding mongo helper for json dumping (mmccune@redhat.com)
- Grinder: before fetching the repodata convert the url to ascii so urlgrabber
  doesnt freakout (pkilambi@redhat.com)
- encode urls to ascii to please urlgrabber (pkilambi@redhat.com)
- logging info change, as per QE request (jmatthew@redhat.com)

* Fri May 21 2010 Adam Young <ayoung@redhat.com> 0.0.3-2
- Added dependencies 
  
* Thu May 20 2010 Adam Young <ayoung@redhat.com> 0.0.3-1
- fixed call to setup to install all files

* Thu May 20 2010 Mike McCune <mmccune@redhat.com> 0.0.2-1
- tito tagging

* Thu May 20 2010 Adam Young 0.0.3-1
- Use macro for file entry for juicer
- strip leading line from files that are not supposed to be scripts 

* Wed May 19 2010 Adam Young  <ayoung@redhat.com> - 0.0.1
- Initial specfile
